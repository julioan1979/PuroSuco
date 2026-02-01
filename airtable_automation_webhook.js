/**
 * AIRTABLE AUTOMATION SCRIPT - STRIPE WEBHOOK HANDLER
 * =====================================================
 * 
 * Este script processa webhooks do Stripe em TEMPO REAL e insere/atualiza dados no Airtable.
 * Evita duplicações verificando se o registro já existe ANTES de criar.
 * 
 * COMO USAR:
 * ==========================================
 * 1. No Airtable Dashboard, ir a "Automations"
 * 2. Clicar "Create new"  selecionar "When webhook received"
 * 3. Copiar a WEBHOOK URL do Airtable
 * 4. No Stripe Dashboard > Webhooks, adicionar novo endpoint
 *    - URL: [cole a webhook URL do Airtable]
 *    - Events: charge.succeeded, payment_intent.succeeded, checkout.session.completed, customer.updated
 * 5. De volta no Airtable, adicionar "Run script" action
 * 6. Colar este código todo na janela de código
 * 7. Ativar a automation (toggle "On")
 * 
 * EVENTOS SUPORTADOS:
 * ==========================================
 * - charge.succeeded        Popula tabela Charges
 * - payment_intent.succeeded  Popula tabela Payment_Intents
 * - checkout.session.completed  Popula tabela Checkout_Sessions
 * - customer.created / customer.updated  Popula tabela Customers
 * 
 * ANTI-DUPLICAÇÃO:
 * ==========================================
 * - Cada evento é verificado por event_id (único do Stripe)
 * - Charges verificadas por charge_id
 * - Payment Intents verificadas por payment_intent_id
 * - Checkout Sessions verificadas por session_id
 * - Customers verificadas por email ou customer_id
 */

// INPUT - Receber webhook
let inputConfig = input.config();
let event = inputConfig.body || inputConfig;

if (typeof event === "string") {
    try {
        event = JSON.parse(event);
    } catch (e) {
        output.set("error", "Invalid JSON payload");
        throw new Error("Invalid JSON: " + e.message);
    }
}

// TABLES - Referenciar tabelas
let tblEvents = base.getTable("Stripe_Events");
let tblCharges = base.getTable("Charges");
let tblPaymentIntents = base.getTable("Payment_Intents");
let tblSessions = base.getTable("Checkout_Sessions");
let tblCustomers = base.getTable("Customers");

// HELPER FUNCTIONS
async function findRecord(table, field, value) {
    if (!value) return null;
    try {
        let query = await table.selectRecordsAsync({ fields: [field] });
        return query.records.find(r => r.getCellValue(field) === value);
    } catch (e) {
        console.log(\[ERROR] findRecord: \=\ - \\);
        return null;
    }
}

function ts(sec) {
    if (!sec) return null;
    return new Date(sec * 1000);
}

function getEmail(obj) {
    return obj.billing_details?.email || obj.customer_details?.email || obj.email || null;
}

function getName(obj) {
    return obj.billing_details?.name || obj.customer_details?.name || obj.name || null;
}

function formatAddress(address) {
    if (!address) return null;
    return [address.line1, address.line2, address.city, address.postal_code, address.state, address.country].filter(Boolean).join(", ");
}

// MAIN PROCESSING
let obj = event.data?.object || {};
let eventType = event.type;

console.log(\[START] Processing webhook: \ | Event ID: \\);

// STRIPE EVENTS (Audit Log)
let existingEvent = await findRecord(tblEvents, "event_id", event.id);

if (!existingEvent) {
    try {
        await tblEvents.createRecordAsync({
            "event_id": event.id,
            "type": eventType,
            "created_at": ts(event.created),
            "livemode": event.livemode || false,
            "api_version": event.api_version,
            "account": event.account,
            "request_id": event.request?.id,
            "idempotency_key": event.request?.idempotency_key,
            "pending_webhooks": event.pending_webhooks || 0,
            "data_object_id": obj.id,
            "data_object_type": obj.object,
            "payload_json": JSON.stringify(event, null, 2)
        });
        console.log(\[SUCCESS] Event logged: \\);
    } catch (e) {
        console.log(\[ERROR] Creating event: \\);
    }
}

// CUSTOMER UPSERT
async function upsertCustomer(customerId, name, email, phone, address) {
    if (!email && !customerId) return false;

    let searchField = email ? "email" : "customer_id";
    let searchValue = email || customerId;
    let existingCustomer = await findRecord(tblCustomers, searchField, searchValue);

    let customerData = {
        "customer_id": customerId || email,
        "name": name,
        "email": email,
        "phone": phone,
        "address": formatAddress(address)
    };

    try {
        if (!existingCustomer) {
            await tblCustomers.createRecordAsync(customerData);
            console.log(\[SUCCESS] Customer created: \\);
            return true;
        } else {
            let updates = {};
            for (let [key, value] of Object.entries(customerData)) {
                if (value && !existingCustomer.getCellValue(key)) {
                    updates[key] = value;
                }
            }
            if (Object.keys(updates).length > 0) {
                await tblCustomers.updateRecordAsync(existingCustomer.id, updates);
                console.log(\[SUCCESS] Customer updated: \\);
                return true;
            }
        }
    } catch (e) {
        console.log(\[ERROR] Upsert customer: \\);
        return false;
    }
}

// CHARGE PROCESSING
if (eventType === "charge.succeeded" || obj.object === "charge") {
    let chargeId = obj.id;
    let existingCharge = await findRecord(tblCharges, "charge_id", chargeId);

    if (!existingCharge) {
        try {
            await tblCharges.createRecordAsync({
                "charge_id": chargeId,
                "created_at": ts(obj.created),
                "status": obj.status,
                "amount": obj.amount ? obj.amount / 100 : null,
                "currency": obj.currency?.toUpperCase(),
                "customer_id": obj.customer,
                "customer_email": getEmail(obj),
                "billing_name": getName(obj),
                "billing_phone": obj.billing_details?.phone,
                "billing_address": formatAddress(obj.billing_details?.address),
                "description": obj.description,
                "statement_descriptor": obj.statement_descriptor,
                "calculated_statement_descriptor": obj.calculated_statement_descriptor,
                "invoice_id": obj.invoice,
                "payment_intent_id": obj.payment_intent,
                "receipt_url": obj.receipt_url,
                "livemode": obj.livemode || false
            });
            console.log(\[SUCCESS] Charge created: \\);

            await upsertCustomer(obj.customer, getName(obj), getEmail(obj), obj.billing_details?.phone, obj.billing_details?.address);
        } catch (e) {
            console.log(\[ERROR] Creating charge: \\);
        }
    }
}

// PAYMENT INTENT PROCESSING
if (eventType === "payment_intent.succeeded" || obj.object === "payment_intent") {
    let piId = obj.id;
    let existingPI = await findRecord(tblPaymentIntents, "payment_intent_id", piId);

    let chargeId = null;
    let receiptUrl = null;
    if (obj.charges?.data && obj.charges.data.length > 0) {
        chargeId = obj.charges.data[0].id;
        receiptUrl = obj.charges.data[0].receipt_url;
    }

    if (!existingPI) {
        try {
            await tblPaymentIntents.createRecordAsync({
                "payment_intent_id": piId,
                "created_at": ts(obj.created),
                "status": obj.status,
                "amount": obj.amount ? obj.amount / 100 : null,
                "currency": obj.currency?.toUpperCase(),
                "customer_id": obj.customer,
                "charge_id": chargeId,
                "receipt_url": receiptUrl,
                "livemode": obj.livemode || false
            });
            console.log(\[SUCCESS] Payment Intent created: \\);
        } catch (e) {
            console.log(\[ERROR] Creating payment_intent: \\);
        }
    }
}

// CHECKOUT SESSION PROCESSING
if (eventType === "checkout.session.completed" || obj.object === "checkout.session") {
    let sessionId = obj.id;
    let existingSession = await findRecord(tblSessions, "session_id", sessionId);

    let customerDetails = obj.customer_details || {};
    let customerId = obj.customer || customerDetails.email;

    if (!existingSession) {
        try {
            await tblSessions.createRecordAsync({
                "session_id": sessionId,
                "created_at": ts(obj.created),
                "status": obj.status,
                "mode": obj.mode,
                "amount_total": obj.amount_total ? obj.amount_total / 100 : null,
                "currency": obj.currency?.toUpperCase(),
                "customer_id": customerId,
                "customer_email": customerDetails.email,
                "payment_intent_id": obj.payment_intent,
                "client_reference_id": obj.client_reference_id,
                "receipt_url": obj.receipt_url,
                "livemode": obj.livemode || false
            });
            console.log(\[SUCCESS] Checkout Session created: \\);

            await upsertCustomer(customerId, customerDetails.name, customerDetails.email, customerDetails.phone, customerDetails.address);
        } catch (e) {
            console.log(\[ERROR] Creating checkout_session: \\);
        }
    }
}

// CUSTOMER EVENTS
if (eventType.startsWith("customer.")) {
    await upsertCustomer(obj.id, obj.name, obj.email, obj.phone, obj.address);
}

output.set("success", true);
output.set("event_type", eventType);
output.set("event_id", event.id);
console.log(\[DONE] Webhook processed: \\);
