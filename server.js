import express from "express";
import Stripe from "stripe";
import fetch from "node-fetch";

const env = process.env;
const STRIPE_API_KEY = env.STRIPE_API_KEY;
const STRIPE_WEBHOOK_SECRET = env.STRIPE_WEBHOOK_SECRET;
const BASE_ID = env.AIRTABLE_BASE_ID || env.Airtable_Base_ID || "";
const AIRTABLE_TOKEN = env.AIRTABLE_PAT || env.Airtable_API_Key || "";
const PORT = env.PORT || 8080;

const TABLES = {
  pagamentosManual: "tblnr8izCueFyCXNk",
  stripeEvents: "tblwyYkn8VPihm75i",
  charges: "tblJT0DPnu3bJ4G2L",
  paymentIntents: "tblskvOI0KbWSyGIs",
  checkoutSessions: "tbls5qaEcZB8SQJ25",
  customers: "tblZgz6ePSa0UuQV4",
  payouts: "tblpeue5OaJt73kpR",
  tickets: "tblm62I2PZlfavBH4",
  qrcodes: "tblNYyPQnQ8fFJLz5",
  logs: "tblxBoOBHvIwFTqE4",
  receipts: "tblKdBsl91xMM44Gd"
};

if (!STRIPE_API_KEY || !STRIPE_WEBHOOK_SECRET || !BASE_ID || !AIRTABLE_TOKEN) {
  console.warn("Missing env vars: STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET, AIRTABLE_BASE_ID/Airtable_Base_ID, AIRTABLE_PAT/Airtable_API_Key");
}

const app = express();
const stripe = new Stripe(STRIPE_API_KEY);

function ts(sec) {
  if (!sec) return null;
  return new Date(sec * 1000).toISOString();
}

function getEmail(obj) {
  if (!obj) return null;
  if (obj.billing_details && obj.billing_details.email) return obj.billing_details.email;
  if (obj.customer_details && obj.customer_details.email) return obj.customer_details.email;
  return obj.email || null;
}

function getName(obj) {
  if (!obj) return null;
  if (obj.billing_details && obj.billing_details.name) return obj.billing_details.name;
  if (obj.customer_details && obj.customer_details.name) return obj.customer_details.name;
  return obj.name || null;
}

function formatAddress(address) {
  if (!address) return null;
  var parts = [];
  if (address.line1) parts.push(address.line1);
  if (address.line2) parts.push(address.line2);
  if (address.city) parts.push(address.city);
  if (address.postal_code) parts.push(address.postal_code);
  if (address.state) parts.push(address.state);
  if (address.country) parts.push(address.country);
  return parts.join(", ");
}

function airtableEscape(value) {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, "\\\"");
}

async function airtableRequest(method, tableId, body, query) {
  const url = "https://api.airtable.com/v0/" + BASE_ID + "/" + tableId + (query || "");
  const res = await fetch(url, {
    method: method,
    headers: {
      Authorization: "Bearer " + AIRTABLE_TOKEN,
      "Content-Type": "application/json"
    },
    body: body ? JSON.stringify(body) : undefined
  });

  const data = await res.json();
  if (!res.ok) {
    const err = new Error(JSON.stringify(data));
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
}

async function findRecordId(tableId, fieldName, value) {
  if (!value) return null;
  const formula = "{" + fieldName + "}=\"" + airtableEscape(value) + "\"";
  const query = "?maxRecords=1&filterByFormula=" + encodeURIComponent(formula) + "&fields%5B%5D=" + encodeURIComponent(fieldName);
  const data = await airtableRequest("GET", tableId, null, query);
  return data.records && data.records.length > 0 ? data.records[0].id : null;
}

async function logToAirtable(payload) {
  try {
    const logId = "log_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
    await airtableRequest("POST", TABLES.logs, {
      records: [
        {
          fields: {
            log_id: logId,
            level: payload.level || "INFO",
            module: payload.module || "webhook",
            action: payload.action || "process",
            status: payload.status || "success",
            message: payload.message || "",
            user_id: payload.userId || null,
            object_type: payload.objectType || null,
            object_id: payload.objectId || null,
            error_details: payload.errorDetails || null,
            timestamp: new Date().toISOString()
          }
        }
      ]
    });
  } catch (err) {
    console.error("Log write failed:", err.message);
  }
}

async function upsertAirtable(tableId, fields, mergeOn, logMeta) {
  try {
    if (mergeOn) {
      const payload = {
        records: [{ fields: fields }],
        performUpsert: { fieldsToMergeOn: [mergeOn] }
      };
      const data = await airtableRequest("POST", tableId, payload);
      return data.records && data.records[0] ? data.records[0].id : null;
    }

    const data = await airtableRequest("POST", tableId, { records: [{ fields: fields }] });
    return data.records && data.records[0] ? data.records[0].id : null;
  } catch (err) {
    if (mergeOn && err.status === 422) {
      const recordId = await findRecordId(tableId, mergeOn, fields[mergeOn]);
      if (recordId) {
        const data = await airtableRequest("PATCH", tableId, {
          records: [{ id: recordId, fields: fields }]
        });
        return data.records && data.records[0] ? data.records[0].id : recordId;
      }
      const data = await airtableRequest("POST", tableId, { records: [{ fields: fields }] });
      return data.records && data.records[0] ? data.records[0].id : null;
    }

    await logToAirtable({
      level: "ERROR",
      module: "airtable",
      action: "upsert",
      status: "failed",
      message: err.message,
      objectType: logMeta ? logMeta.objectType : null,
      objectId: logMeta ? logMeta.objectId : null,
      errorDetails: err.payload ? JSON.stringify(err.payload) : err.message
    });
    throw err;
  }
}

async function logEventToAirtable(event) {
  const obj = event.data && event.data.object ? event.data.object : {};
  const fields = {
    event_id: event.id,
    type: event.type,
    api_version: event.api_version,
    account: event.account || null,
    request_id: event.request && event.request.id ? event.request.id : null,
    idempotency_key: event.request && event.request.idempotency_key ? event.request.idempotency_key : null,
    data_object_id: obj.id || null,
    data_object_type: obj.object || null,
    payload_json: JSON.stringify(event),
    created_at: ts(event.created),
    livemode: event.livemode || false,
    pending_webhooks: event.pending_webhooks || 0
  };

  return upsertAirtable(TABLES.stripeEvents, fields, "event_id", {
    objectType: "stripe_event",
    objectId: event.id
  });
}

async function upsertCustomerFromObject(obj) {
  const customerId = (obj && (obj.customer || obj.id)) || null;
  const email = getEmail(obj);
  const fields = {
    customer_id: customerId || email,
    name: getName(obj),
    email: email,
    phone: (obj && obj.billing_details && obj.billing_details.phone) ? obj.billing_details.phone : (obj ? obj.phone : null),
    address: formatAddress((obj && obj.billing_details && obj.billing_details.address) ? obj.billing_details.address : (obj ? obj.address : null))
  };

  if (!fields.customer_id) return null;

  return upsertAirtable(TABLES.customers, fields, "customer_id", {
    objectType: "customer",
    objectId: fields.customer_id
  });
}

async function handleCharge(obj) {
  const chargeId = obj.id;
  const fields = {
    charge_id: chargeId,
    created_at: ts(obj.created),
    status: obj.status,
    amount: obj.amount ? obj.amount / 100 : null,
    currency: obj.currency ? String(obj.currency).toUpperCase() : null,
    customer_id: obj.customer,
    customer_email: getEmail(obj),
    billing_name: getName(obj),
    billing_phone: obj.billing_details ? obj.billing_details.phone : null,
    billing_address: formatAddress(obj.billing_details ? obj.billing_details.address : null),
    description: obj.description,
    statement_descriptor: obj.statement_descriptor,
    calculated_statement_descriptor: obj.calculated_statement_descriptor,
    invoice_id: obj.invoice,
    payment_intent_id: obj.payment_intent,
    receipt_url: obj.receipt_url,
    livemode: obj.livemode || false
  };

  await upsertAirtable(TABLES.charges, fields, "charge_id", {
    objectType: "charge",
    objectId: chargeId
  });

  await upsertCustomerFromObject(obj);

  const pagamentoFields = {
    Name: getName(obj),
    Convidado: getName(obj),
    "Valor Pago": obj.amount ? obj.amount / 100 : null,
    "Metodo de Pagamento": obj.payment_method_details ? obj.payment_method_details.type : null,
    "Data do Pagamento": ts(obj.created),
    "Status do Pagamento": obj.status || null,
    Observacoes: chargeId ? "Stripe charge_id: " + chargeId : null,
    Quantidade: obj.metadata && obj.metadata.quantity ? Number(obj.metadata.quantity) : null,
    Email: getEmail(obj),
    Phone: obj.billing_details ? obj.billing_details.phone : null
  };

  if (pagamentoFields.Observacoes) {
    await upsertAirtable(TABLES.pagamentosManual, pagamentoFields, "Observacoes", {
      objectType: "pagamento_manual",
      objectId: pagamentoFields.Observacoes
    });
  }
}

async function handlePaymentIntent(obj) {
  const piId = obj.id;
  let chargeId = null;
  let receiptUrl = null;
  if (obj.charges && obj.charges.data && obj.charges.data.length > 0) {
    chargeId = obj.charges.data[0].id;
    receiptUrl = obj.charges.data[0].receipt_url || null;
  }

  const fields = {
    payment_intent_id: piId,
    created_at: ts(obj.created),
    status: obj.status,
    amount: obj.amount ? obj.amount / 100 : null,
    currency: obj.currency ? String(obj.currency).toUpperCase() : null,
    customer_id: obj.customer,
    charge_id: chargeId,
    receipt_url: receiptUrl,
    livemode: obj.livemode || false
  };

  await upsertAirtable(TABLES.paymentIntents, fields, "payment_intent_id", {
    objectType: "payment_intent",
    objectId: piId
  });
}

async function handleCheckoutSession(obj) {
  const sessionId = obj.id;
  const customerDetails = obj.customer_details || {};
  const customerId = obj.customer || customerDetails.email || null;

  const fields = {
    session_id: sessionId,
    created_at: ts(obj.created),
    status: obj.status,
    mode: obj.mode,
    amount_total: obj.amount_total ? obj.amount_total / 100 : null,
    currency: obj.currency ? String(obj.currency).toUpperCase() : null,
    customer_id: customerId,
    customer_email: customerDetails.email || null,
    payment_intent_id: obj.payment_intent,
    client_reference_id: obj.client_reference_id,
    receipt_url: obj.receipt_url,
    livemode: obj.livemode || false
  };

  await upsertAirtable(TABLES.checkoutSessions, fields, "session_id", {
    objectType: "checkout_session",
    objectId: sessionId
  });

  await upsertCustomerFromObject({
    id: customerId,
    name: customerDetails.name,
    email: customerDetails.email,
    phone: customerDetails.phone,
    address: customerDetails.address
  });
}

async function handlePayout(obj) {
  const payoutId = obj.id;
  const fields = {
    payout_id: payoutId,
    status: obj.status,
    currency: obj.currency ? String(obj.currency).toUpperCase() : null,
    created_at: ts(obj.created),
    arrival_date: ts(obj.arrival_date),
    amount: obj.amount ? obj.amount / 100 : null
  };

  await upsertAirtable(TABLES.payouts, fields, "payout_id", {
    objectType: "payout",
    objectId: payoutId
  });
}

async function processStripeEvent(event) {
  await logEventToAirtable(event);

  const obj = event.data && event.data.object ? event.data.object : {};
  const eventType = event.type || "";

  if (eventType.indexOf("charge.") === 0) {
    await handleCharge(obj);
    return;
  }

  if (eventType.indexOf("payment_intent.") === 0) {
    await handlePaymentIntent(obj);
    return;
  }

  if (eventType.indexOf("checkout.session.") === 0) {
    await handleCheckoutSession(obj);
    return;
  }

  if (eventType.indexOf("customer.") === 0) {
    await upsertCustomerFromObject(obj);
    return;
  }

  if (eventType.indexOf("payout.") === 0) {
    await handlePayout(obj);
  }
}

app.post("/stripe/webhook", express.raw({ type: "application/json" }), async function (req, res) {
  const sig = req.headers["stripe-signature"];
  let event;

  try {
    event = stripe.webhooks.constructEvent(req.body, sig, STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.error("Stripe signature invalid:", err.message);
    await logToAirtable({
      level: "ERROR",
      module: "webhook",
      action: "verify_signature",
      status: "failed",
      message: err.message,
      errorDetails: err.stack
    });
    return res.status(400).send("Invalid signature");
  }

  console.log("Stripe event:", event.type, event.id);

  try {
    await processStripeEvent(event);
    await logToAirtable({
      level: "INFO",
      module: "webhook",
      action: event.type,
      status: "success",
      message: "Event processed: " + event.type,
      objectType: event.data && event.data.object ? event.data.object.object : null,
      objectId: event.data && event.data.object ? event.data.object.id : null
    });
  } catch (err) {
    console.error("Webhook processing error:", err.message);
    await logToAirtable({
      level: "ERROR",
      module: "webhook",
      action: event.type,
      status: "failed",
      message: err.message,
      objectType: event.data && event.data.object ? event.data.object.object : null,
      objectId: event.data && event.data.object ? event.data.object.id : null,
      errorDetails: err.stack
    });
  }

  res.sendStatus(200);
});

app.get("/", function (_, res) {
  res.send("Stripe webhook server OK");
});

app.get("/health", function (_, res) {
  res.json({ status: "healthy", service: "stripe-webhook" });
});

app.listen(PORT, function () {
  console.log("Server running on port " + PORT);
});
