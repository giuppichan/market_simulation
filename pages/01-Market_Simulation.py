# to run the app:
# streamlit run Home.py

# developments related this version
# 1) web deployment

import streamlit as st
import pandas as pd
import numpy as np
import simpy
import altair as alt
import random

class Buyer(object):
    def __init__ (self, env, name, market):
        self.env, self.name = env, name
        self.market = market
        self.consumption = random.randint(1, 20)
        self.quantity = 0
        self.price = random.randint(self.market.initial_parameters["min_price"], self.market.initial_parameters["max_price"])
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
                if self.price < self.market.max_price:
                    self.price = random.randint(self.price, self.market.max_price)
            self.quantity = 0 # no stock

            yield self.env.timeout(1) # optional, priority can be added heere to set manually the order of execution
    
class Seller(object):
    def __init__ (self, env, name, market):
        self.env, self.name = env, name
        self.market = market
        self.production = random.randint(1, 20)
        self.quantity = 0
        self.price = random.randint(self.market.initial_parameters["min_price"], self.market.initial_parameters["max_price"])
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
                if self.price > self.market.min_price:
                    self.price = random.randint(self.market.min_price, self.price)
            self.quantity = self.production
            yield self.env.timeout(1)
            
class Market (object):
    def __init__ (self, env, num_buyer, num_seller, min_price, max_price):
        self.env = env
        self.buyers_list = []
        self.sellers_list = []
        self.buyers_df = pd.DataFrame()
        self.sellers_df = pd.DataFrame()
        self.market_df = pd.DataFrame()
        # initial parameters needed to reset min and max prices every market cycle
        # it's used to set buyer and seller initial price
        self.initial_parameters = {
            "min_price": min_price,
            "max_price": max_price}
        # store price range of a market cycle
        self.min_price = min_price
        self.max_price = max_price

        for i in range(1, num_buyer+1):
            b=Buyer(env, "Buyer n.%d" % i, self)
            self.buyers_list.append(b)
            self.buyers_df = pd.concat([
                self.buyers_df, pd.DataFrame.from_dict([b.status()])
                ], ignore_index=True)
        print("buyers created")
        
        for i in range(1, num_seller+1):
            s=Seller(env, "Seller n.%d" % i, self)
            self.sellers_list.append(s)
            self.sellers_df = pd.concat([
                self.sellers_df, pd.DataFrame.from_dict([s.status()])
                ], ignore_index=True)
        print("sellers created")

        self.action = env.process(self.trade())
        print('market created')
        
    def trade(self): # goods exchange

        while True:
            random.shuffle(self.buyers_list)
            random.shuffle(self.sellers_list)
            self.min_price=None # self.initial_parameters["min_price"]
            self.max_price=None # self.initial_parameters["max_price"]
            
            for s in self.sellers_list:
                for b in self.buyers_list:
                    while (s.quantity>0) & (b.consumption-b.quantity>0) & (b.price>=s.price): # conditions to make the deal

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

            yield self.env.timeout(1)


# st.set_page_config(layout="wide")
st.title("Market simulation")

num_seller = st.number_input(
    "Number of sellers", min_value=1, max_value=50, value=10  )

num_buyer = st.number_input(
    "Number of buyers", min_value=1, max_value=50, value=10  )

min_price, max_price = st.slider("Price Range", min_value=1, max_value=100, value=(25, 75), step=1, key="price_range")

num_iteration = st.number_input(
    "Number of market iterations", min_value=1, max_value=200, value=50  )

start = st.button("Start Market Simulation")
if start:
    env = simpy.Environment()
    m = Market(env, num_buyer, num_seller, min_price, max_price)

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
