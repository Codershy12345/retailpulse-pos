import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="RetailPulse Local POS", layout="centered")

DB_FILE = "retailpulse.db"

# Local SQLite connection & table auto-creation
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Dim_Product (
            ProductID INTEGER PRIMARY KEY AUTOINCREMENT,
            ProductName TEXT,
            Category TEXT,
            MRP REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Fact_Inventory_Batches (
            BatchID INTEGER PRIMARY KEY AUTOINCREMENT,
            ProductID INTEGER,
            BatchNumber TEXT,
            StockOnHand INTEGER,
            ExpiryDate TEXT,
            FOREIGN KEY (ProductID) REFERENCES Dim_Product (ProductID)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Fact_Sales_Header (
            BillID INTEGER PRIMARY KEY AUTOINCREMENT,
            BillDateTime TEXT,
            PaymentMode TEXT,
            SubTotal REAL,
            TotalDiscount REAL,
            GrandTotal REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Fact_Sales_Lines (
            LineID INTEGER PRIMARY KEY AUTOINCREMENT,
            BillID INTEGER,
            ProductID INTEGER,
            BatchID INTEGER,
            QuantitySold INTEGER,
            UnitPrice REAL,
            LineDiscount REAL,
            LineTotal REAL,
            FOREIGN KEY (BillID) REFERENCES Fact_Sales_Header (BillID)
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM Dim_Product")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO Dim_Product (ProductName, Category, MRP) VALUES ('Amul Butter 500g', 'Dairy', 275.0)")
        cursor.execute("INSERT INTO Dim_Product (ProductName, Category, MRP) VALUES ('Tata Tea Premium 1kg', 'Packaged Food', 450.0)")
        cursor.execute("INSERT INTO Dim_Product (ProductName, Category, MRP) VALUES ('Maggi 2-Minute Noodles 70g', 'Packaged Food', 14.0)")
        
        cursor.execute("INSERT INTO Fact_Inventory_Batches (ProductID, BatchNumber, StockOnHand, ExpiryDate) VALUES (1, 'BAT-BUT-01', 30, '2026-10-04')")
        cursor.execute("INSERT INTO Fact_Inventory_Batches (ProductID, BatchNumber, StockOnHand, ExpiryDate) VALUES (2, 'BAT-TEA-01', 25, '2027-09-25')")
        cursor.execute("INSERT INTO Fact_Inventory_Batches (ProductID, BatchNumber, StockOnHand, ExpiryDate) VALUES (3, 'BAT-MAG-01', 100, '2027-03-24')")
        
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_FILE)

st.title("🛒 RetailPulse - Local POS Counter")
st.caption("🔒 100% Offline & Private - Saara data aapke device par locally saved hai.")

conn = get_connection()
products_df = pd.read_sql("SELECT ProductID, ProductName, Category, MRP FROM Dim_Product", conn)
conn.close()

product_names = products_df['ProductName'].tolist()
selected_product = st.selectbox("Product Chuno", product_names)

prod_info = products_df[products_df['ProductName'] == selected_product].iloc[0]
st.write(f"**Category:** {prod_info['Category']} | **Price:** ₹{prod_info['MRP']}")

qty = st.number_input("Quantity", min_value=1, value=1, step=1)
discount = st.number_input("Discount (₹)", min_value=0.0, value=0.0, step=5.0)
payment_mode = st.selectbox("Payment Mode", ["UPI", "Cash", "Card"])

total_amount = max(0.0, float(prod_info['MRP'] * qty - discount))
st.subheader(f"Total Amount: ₹{total_amount:.2f}")

if st.button("Complete Sale / Bill Banao", type="primary"):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT BatchID, StockOnHand 
        FROM Fact_Inventory_Batches 
        WHERE ProductID = ? AND StockOnHand >= ?
        ORDER BY ExpiryDate ASC LIMIT 1
    """, (int(prod_info['ProductID']), qty))
    
    batch = cursor.fetchone()
    
    if not batch:
        st.error("Is item ka required stock available nahi hai!")
        conn.close()
    else:
        batch_id = batch[0]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO Fact_Sales_Header (BillDateTime, PaymentMode, SubTotal, TotalDiscount, GrandTotal)
            VALUES (?, ?, ?, ?, ?)
        """, (now_str, payment_mode, float(prod_info['MRP'] * qty), discount, total_amount))
        bill_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO Fact_Sales_Lines (BillID, ProductID, BatchID, QuantitySold, UnitPrice, LineDiscount, LineTotal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (bill_id, int(prod_info['ProductID']), batch_id, qty, float(prod_info['MRP']), discount, total_amount))
        
        cursor.execute("""
            UPDATE Fact_Inventory_Batches 
            SET StockOnHand = StockOnHand - ? 
            WHERE BatchID = ?
        """, (qty, batch_id))
        
        conn.commit()
        conn.close()
        
        st.success(f"Bill #{bill_id} ban gaya! Stock deduct ho chuka hai.")
        st.balloons()

st.sidebar.header("📦 Local Inventory Status")
conn = get_connection()
stock_df = pd.read_sql("""
    SELECT p.ProductName, b.BatchNumber, b.StockOnHand, b.ExpiryDate
    FROM Fact_Inventory_Batches b
    JOIN Dim_Product p ON b.ProductID = p.ProductID
""", conn)
conn.close()
st.sidebar.dataframe(stock_df, hide_index=True)