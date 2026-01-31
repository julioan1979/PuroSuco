import os
import stripe
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

# Load environment variables

load_dotenv()
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
if not STRIPE_API_KEY:
    st.error('Stripe API key not found. Please check your .env file.')
    st.stop()

stripe.api_key = STRIPE_API_KEY



# --- MENU LATERAL ---
st.set_page_config(page_title='Stripe Dashboard', layout='wide')
st.sidebar.title('Stripe Dashboard')
menu = st.sidebar.radio('Navegação', [
    'Resumo',
    'Vendas',
    'Clientes',
    'Recebimentos',
    'Gráficos',
    'Detalhes'
])

st.title('Stripe Data Analysis')

# Fetch customers
def get_customers(limit=20):
    return stripe.Customer.list(limit=limit)['data']

# Fetch charges (purchases)


# Buscar invoices (faturas) completas
def get_invoices(limit=20):
    return stripe.Invoice.list(limit=limit, expand=["data.customer", "data.lines.data.price"])['data']

# Buscar charges (pagamentos avulsos)
def get_charges(limit=50):
    return stripe.Charge.list(limit=limit, expand=["data.customer"])['data']


# --- RESUMO DAS VENDAS ---
st.header('Resumo das Vendas')
charges = get_charges(limit=100)
invoices = get_invoices(limit=100)

# Unificar vendas (charges e invoices)
sales_data = []
for ch in charges:
    sales_data.append({
        'id': ch.get('id'),
        'tipo': 'Charge',
        'valor': ch.get('amount', 0)/100,
        'moeda': ch.get('currency', '').upper(),
        'status': ch.get('status', 'N/A'),
        'data': pd.to_datetime(ch.get('created', 0), unit='s'),
        'cliente': ch.get('billing_details', {}).get('email', ch.get('customer', 'N/A')),
        'descricao': ch.get('description', 'N/A')
    })
for inv in invoices:
    sales_data.append({
        'id': inv.get('id'),
        'tipo': 'Invoice',
        'valor': inv.get('amount_paid', 0)/100,
        'moeda': inv.get('currency', '').upper(),
        'status': inv.get('status', 'N/A'),
        'data': pd.to_datetime(inv.get('created', 0), unit='s'),
        'cliente': inv.get('customer', {}).get('email', 'N/A') if isinstance(inv.get('customer'), dict) else inv.get('customer', 'N/A'),
        'descricao': 'Invoice'
    })
df_sales = pd.DataFrame(sales_data)

total_vendas = df_sales['valor'].sum()
num_vendas = len(df_sales)
ticket_medio = total_vendas / num_vendas if num_vendas > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric('Total Vendido', f"€ {total_vendas:.2f}")
col2.metric('Nº de Vendas', num_vendas)
col3.metric('Ticket Médio', f"€ {ticket_medio:.2f}")

# --- GRÁFICOS ---
st.subheader('Gráficos de Vendas')
if not df_sales.empty:
    fig = px.bar(df_sales, x='data', y='valor', color='tipo', title='Vendas ao Longo do Tempo')
    st.plotly_chart(fig, use_container_width=True)
    fig2 = px.pie(df_sales, names='status', values='valor', title='Distribuição por Status')
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info('Nenhuma venda encontrada para exibir gráficos.')


# --- TABELA DE VENDAS ---
st.header('Tabelas de Gestão')
st.subheader('Todas as Vendas')
if not df_sales.empty:
    st.dataframe(df_sales[['id','tipo','valor','moeda','status','data','cliente','descricao']].sort_values('data', ascending=False), use_container_width=True)
else:
    st.info('Nenhuma venda encontrada para exibir tabela.')

# --- TABELA DE CLIENTES ---
st.subheader('Todos os Clientes')
clientes = get_customers(limit=100)
clientes_data = []
for c in clientes:
    email = c.get('email', 'N/A')
    name = c.get('name', 'N/A')
    customer_id = c.get('id')
    # Total comprado e nº de compras
    compras_cliente = df_sales[df_sales['cliente'].astype(str).str.contains(email if email != 'N/A' else customer_id)]
    total_comprado = compras_cliente['valor'].sum()
    num_compras = len(compras_cliente)
    clientes_data.append({
        'id': customer_id,
        'nome': name,
        'email': email,
        'total_comprado': total_comprado,
        'num_compras': num_compras
    })
df_clientes = pd.DataFrame(clientes_data)
if not df_clientes.empty:
    st.dataframe(df_clientes[['id','nome','email','total_comprado','num_compras']].sort_values('total_comprado', ascending=False), use_container_width=True)
else:


    # --- DADOS BASE COM TRATAMENTO DE ERRO ---
    stripe_error = None
    charges, invoices, df_sales, df_clientes, df_payouts = [], [], pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        charges = get_charges(limit=100)
        invoices = get_invoices(limit=100)
        sales_data = []
        for ch in charges:
            sales_data.append({
                'id': ch.get('id'),
                'tipo': 'Charge',
                'valor': ch.get('amount', 0)/100,
                'moeda': ch.get('currency', '').upper(),
                'status': ch.get('status', 'N/A'),
                'data': pd.to_datetime(ch.get('created', 0), unit='s'),
                'cliente': ch.get('billing_details', {}).get('email', ch.get('customer', 'N/A')),
                'descricao': ch.get('description', 'N/A')
            })
        for inv in invoices:
            sales_data.append({
                'id': inv.get('id'),
                'tipo': 'Invoice',
                'valor': inv.get('amount_paid', 0)/100,
                'moeda': inv.get('currency', '').upper(),
                'status': inv.get('status', 'N/A'),
                'data': pd.to_datetime(inv.get('created', 0), unit='s'),
                'cliente': inv.get('customer', {}).get('email', 'N/A') if isinstance(inv.get('customer'), dict) else inv.get('customer', 'N/A'),
                'descricao': 'Invoice'
            })
        df_sales = pd.DataFrame(sales_data)
        clientes = get_customers(limit=100)
        clientes_data = []
        for c in clientes:
            email = c.get('email', 'N/A')
            name = c.get('name', 'N/A')
            customer_id = c.get('id')
            compras_cliente = df_sales[df_sales['cliente'].astype(str).str.contains(email if email != 'N/A' else customer_id)]
            total_comprado = compras_cliente['valor'].sum()
            num_compras = len(compras_cliente)
            clientes_data.append({
                'id': customer_id,
                'nome': name,
                'email': email,
                'total_comprado': total_comprado,
                'num_compras': num_compras
            })
        df_clientes = pd.DataFrame(clientes_data)
        payouts = stripe.Payout.list(limit=50)['data']
        payouts_data = []
        for p in payouts:
            payouts_data.append({
                'id': p.get('id'),
                'valor': p.get('amount', 0)/100,
                'moeda': p.get('currency', '').upper(),
                'status': p.get('status', 'N/A'),
                'data': pd.to_datetime(p.get('created', 0), unit='s'),
                'chegada_prevista': pd.to_datetime(p.get('arrival_date', 0), unit='s')
            })
        df_payouts = pd.DataFrame(payouts_data)
    except Exception as e:
        stripe_error = str(e)


    # --- NAVEGAÇÃO POR SEÇÃO ---

    def show_error():
        st.error('Não foi possível conectar à API da Stripe. Verifique sua conexão com a internet, firewall, proxy ou DNS. O menu está disponível, mas os dados não podem ser carregados.')
        if stripe_error:
            st.code(stripe_error)

    if menu == 'Resumo':
        st.header('Resumo das Vendas')
        if stripe_error:
            show_error()
        else:
            total_vendas = df_sales['valor'].sum()
            num_vendas = len(df_sales)
            ticket_medio = total_vendas / num_vendas if num_vendas > 0 else 0
            col1, col2, col3 = st.columns(3)
            col1.metric('Total Vendido', f"€ {total_vendas:.2f}")
            col2.metric('Nº de Vendas', num_vendas)
            col3.metric('Ticket Médio', f"€ {ticket_medio:.2f}")

    elif menu == 'Vendas':
        st.header('Todas as Vendas')
        if stripe_error:
            show_error()
        elif not df_sales.empty:
            st.dataframe(df_sales[['id','tipo','valor','moeda','status','data','cliente','descricao']].sort_values('data', ascending=False), width='stretch')
        else:
            st.info('Nenhuma venda encontrada para exibir tabela.')

    elif menu == 'Clientes':
        st.header('Todos os Clientes')
        if stripe_error:
            show_error()
        elif not df_clientes.empty:
            st.dataframe(df_clientes[['id','nome','email','total_comprado','num_compras']].sort_values('total_comprado', ascending=False), width='stretch')
        else:
            st.info('Nenhum cliente encontrado.')

    elif menu == 'Recebimentos':
        st.header('Recebimentos (Payouts)')
        if stripe_error:
            show_error()
        elif not df_payouts.empty:
            st.dataframe(df_payouts[['id','valor','moeda','status','data','chegada_prevista']].sort_values('data', ascending=False), width='stretch')
        else:
            st.info('Nenhum recebimento encontrado.')

    elif menu == 'Gráficos':
        st.header('Gráficos de Vendas')
        if stripe_error:
            show_error()
        elif not df_sales.empty:
            fig = px.bar(df_sales, x='data', y='valor', color='tipo', title='Vendas ao Longo do Tempo')
            st.plotly_chart(fig, use_container_width=True)
            fig2 = px.pie(df_sales, names='status', values='valor', title='Distribuição por Status')
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info('Nenhuma venda encontrada para exibir gráficos.')

    elif menu == 'Detalhes':
        st.header('Detalhes das Vendas (Invoices)')
        if stripe_error:
            show_error()
        else:
            for inv in invoices:
                with st.expander(f"Fatura: {inv.get('id')}"):
                    cliente = inv.get('customer')
                    if cliente:
                        st.write(f"Cliente: {cliente.get('name', 'N/A')} | Email: {cliente.get('email', 'N/A')}")
                    else:
                        st.write("Cliente: N/A")
                    st.write(f"Status do pagamento: {inv.get('status', 'N/A')}")
                    st.write(f"Valor total: {inv.get('amount_due', 0)/100:.2f} {inv.get('currency', '').upper()}")
                    st.write(f"Valor pago: {inv.get('amount_paid', 0)/100:.2f} {inv.get('currency', '').upper()}")
                    st.write(f"Data de emissão: {pd.to_datetime(inv.get('created', 0), unit='s')}")
                    st.write("Itens:")
                    for item in inv.get('lines', {}).get('data', []):
                        price = item.get('price', {})
                        product_id = price.get('product')
                        nome_produto = 'N/A'
                        if product_id:
                            try:
                                product = stripe.Product.retrieve(product_id)
                                nome_produto = product.get('name', 'N/A')
                            except Exception:
                                pass
                        st.write({
                            'Produto': nome_produto,
                            'Quantidade': item.get('quantity', 1),
                            'Valor unitário': f"{item.get('amount', 0)/100:.2f} {item.get('currency', '').upper()}"
                        })
            st.header('Detalhes das Vendas (Charges)')
            for ch in charges:
                with st.expander(f"Transação: {ch.get('id')}"):
                    customer = ch.get('customer')
                    if isinstance(customer, dict):
                        st.write(f"Cliente: {customer.get('name', 'N/A')} | Email: {customer.get('email', 'N/A')}")
                    else:
                        st.write(f"Cliente ID: {customer if customer else 'N/A'}")
                    st.write(f"Valor: {ch.get('amount', 0)/100:.2f} {ch.get('currency', '').upper()}")
                    st.write(f"Status: {ch.get('status', 'N/A')}")
                    st.write(f"Descrição: {ch.get('description', 'N/A')}")
                    st.write(f"Data: {pd.to_datetime(ch.get('created', 0), unit='s')}")
for ch in charges:
    st.subheader(f"Transação: {ch.get('id')}")
    customer = ch.get('customer')
    if isinstance(customer, dict):
        st.write(f"Cliente: {customer.get('name', 'N/A')} | Email: {customer.get('email', 'N/A')}")
    else:
        st.write(f"Cliente ID: {customer if customer else 'N/A'}")
    st.write(f"Valor: {ch.get('amount', 0)/100:.2f} {ch.get('currency', '').upper()}")
    st.write(f"Status: {ch.get('status', 'N/A')}")
    st.write(f"Descrição: {ch.get('description', 'N/A')}")
    st.write(f"Data: {ch.get('created', 'N/A')}")
    st.markdown('---')
