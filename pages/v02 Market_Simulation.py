# to run the app:
# streamlit run Home.py

# developments related this version
# 1) web deployment
# 2) parameters added as a class

import streamlit as st
import pandas as pd
import numpy as np
import simpy
import altair as alt
import random
from dataclasses import dataclass

class Buyer(object):
    def __init__ (self, env, name, market):
        self.env, self.name, self.market = env, name, market
        self.consumption = random.randint(self.market.config.buyer_min_quantity, self.market.config.buyer_max_quantity)
        self.quantity = 0
        self.price = random.randint(self.market.config.buyer_min_price, self.market.config.buyer_max_price)
        self.action = env.process(self.consume())  # adding grow to env processes. its schedule is determined by yield in the consume function
        
    def status(self):
        return({
            "time":self.env.now,
            "name":self.name,
            "quantity":self.quantity,
            "price":self.price,
            "consumption":self.consumption
            })
        
    def consume(self):
        while True:
            if self.quantity < self.consumption: # cound not satisfy demand
                self.price += 1
                if self.price < self.market.min_price:
                    self.price = random.randint(self.market.min_price, self.market.max_price)
            self.quantity = 0 # no stock

            yield self.env.timeout(1, priority=0) # optional, priority can be added heere to set manually the order of execution
    
class Seller(object):
    def __init__ (self, env, name, market):
        self.env, self.name = env, name
        self.market = market
        self.production = random.randint(self.market.config.seller_min_quantity, self.market.config.seller_max_quantity)
        self.quantity = 0
        self.price = random.randint(self.market.config.seller_min_price, self.market.config.seller_max_price)
        self.action = env.process(self.grow()) # adding grow to env processes. its schedule is determined by yield in the grow function

    def status(self):
        return({
            "time":self.env.now,
            "name":self.name,
            "quantity":self.quantity,
            "price":self.price,
            "production":self.production,
            })
        
    def grow(self):
        while True:
            if self.quantity > 0: #could not sell everything
                self.price -= 1
                if self.price > self.market.max_price:
                    self.price = random.randint(self.market.min_price, self.market.max_price)
            self.quantity = self.production
            yield self.env.timeout(1, priority=0)
            

@dataclass
class MarketConfig:
    num_buyer: int
    num_seller: int
    buyer_min_price: int
    buyer_max_price: int
    buyer_min_quantity: int
    buyer_max_quantity: int
    seller_min_price: int
    seller_max_price: int
    seller_min_quantity: int
    seller_max_quantity: int

class Market (object):
    def __init__ (self, env, config: MarketConfig):
        self.env = env
        self.config = config
        self.buyers_list = []
        self.sellers_list = []
        self.buyers_df = pd.DataFrame()
        self.sellers_df = pd.DataFrame()
        self.market_df = pd.DataFrame()
        # store price range of a market cycle
        self.min_price = None
        self.max_price = None

        for i in range(1, self.config.num_buyer+1):
            b=Buyer(env, f"Buyer n.{i}" % i, self)
            self.buyers_list.append(b)
            self.buyers_df = pd.concat(
                [self.buyers_df, pd.DataFrame.from_dict([b.status()])], 
                ignore_index=True)
        print("buyers created")
        
        for i in range(1, self.config.num_seller+1):
            s=Seller(env, f"Seller n.{i}", self)
            self.sellers_list.append(s)
            self.sellers_df = pd.concat(
                [self.sellers_df, pd.DataFrame.from_dict([s.status()])], 
                ignore_index=True)
        print("sellers created")

        self.action = env.process(self.trade())
        print('market created')
        
    def trade(self): # goods exchange

        while True:
            random.shuffle(self.buyers_list)
            random.shuffle(self.sellers_list)
            self.min_price=None
            self.max_price=None
            
            for s in self.sellers_list:
                for b in self.buyers_list:
                    while (s.quantity>0) and (b.consumption-b.quantity>0) and (b.price>=s.price): # conditions to make the deal

                        traded_quantity = min(s.quantity, b.consumption-b.quantity)
                        deal_price = random.randint(s.price, b.price)
                        s.quantity -= traded_quantity
                        b.quantity += traded_quantity
                        s.price, b.price = deal_price, deal_price
                        
                        if (self.min_price is None) or (deal_price < self.min_price):
                            self.min_price=deal_price
                        if (self.max_price is None) or (deal_price > self.max_price):
                            self.max_price=deal_price
                        
                        self.market_df = pd.concat([ # log the transactions
                            self.market_df, pd.DataFrame.from_dict([{
                                "time":self.env.now,
                                "buyer":b.name,
                                "seller":s.name,
                                "traded_quantity":traded_quantity,
                                "price":deal_price,
                                "min_price":self.min_price,
                                "max_price":self.max_price,
                                }])
                            ], ignore_index=True)

            # log sellers and buyers status after the trade took place
            self.buyers_df = pd.concat([
                self.buyers_df, 
                pd.DataFrame([b.status() for b in self.buyers_list])
                ], ignore_index=True)
            
            self.sellers_df = pd.concat([
                self.sellers_df, 
                pd.DataFrame([s.status() for s in self.sellers_list])
                ], ignore_index=True)

            yield self.env.timeout(1, priority=1)


# st.set_page_config(layout="wide")
st.title("Market simulation")
st.write("This is the baseline market simulation. The dynamics work as follows:")
st.write("- **Seller** and **Buyer** quantity and price ranges are enterable")
st.write("During each turn:")
st.write("- Buyers and Sellers with a positive quantity (or demand) are randomly matched.")
st.write("- If a Seller’s offered price is **lower than or equal to** a Buyer’s payable price, a transaction occurs.")
st.write("- The Buyer purchases as much as possible, up to the Seller’s available quantity and the Buyer’s remaining demand.")
st.write("After each turn Every Seller replenishes their production and Every Buyer replenishes their demand.")
st.write("Price adjustment rules:")
st.write("- A **Buyer** whose demand was not fully satisfied increases its payable price by 1, up to the maximum market price.")
st.write("- A **Seller** with leftover stock decreases its offered price by 1, down to the minimum market price.")

num_seller = st.number_input(
    "Number of sellers", min_value=1, max_value=50, value=10  )
seller_min_quantity, seller_max_quantity = st.slider("Seller Quantity Range", min_value=1, max_value=100, value=(25, 75), step=1, key="seller_quantity_range")
seller_min_price, seller_max_price = st.slider("Seller Price Range", min_value=1, max_value=100, value=(25, 75), step=1, key="seller_price_range")

num_buyer = st.number_input(
    "Number of buyers", min_value=1, max_value=50, value=10  )
buyer_min_quantity, buyer_max_quantity = st.slider("Buyer Quantity Range", min_value=1, max_value=100, value=(25, 75), step=1, key="buyer_quantity_range")
buyer_min_price, buyer_max_price = st.slider("Buyer Price Range", min_value=1, max_value=100, value=(25, 75), step=1, key="buyer_price_range")

num_iteration = st.number_input(
    "Number of market iterations", min_value=1, max_value=200, value=50  )

start = st.button("Start Market Simulation")
if start:
    env = simpy.Environment()

    cfg = MarketConfig(
        num_buyer=num_buyer,
        num_seller=num_seller,
        buyer_min_price=buyer_min_price,
        buyer_max_price=buyer_max_price,
        buyer_min_quantity=buyer_min_quantity,
        buyer_max_quantity=buyer_max_quantity,
        seller_min_price=seller_min_price,
        seller_max_price=seller_max_price,
        seller_min_quantity=seller_min_quantity,
        seller_max_quantity=seller_max_quantity,
    )

    m = Market(env, cfg)

    chart_placeholder = st.empty()
    for step in range(1, num_iteration + 1):
        env.run(until=step)

        # Build Altair chart
        line_chart = (
            alt.Chart(m.buyers_df)
            .mark_line( # type of chart
                color="grey")
            .encode( # data link
                x=alt.X("time:Q", title="Time (steps)"),
                y=alt.Y("price:Q", title="Price"),
                detail="name:N")   # <-- group by buyer name
            .properties(
                width="container",
                height=400,
                title="Buyer Prices and Market Average Over Time"
            )
        )

        # Update chart
        chart_placeholder.altair_chart(line_chart, use_container_width=True)
