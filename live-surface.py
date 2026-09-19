import threading
import time
import pandas as pd
import numpy
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.widgets import Button
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

plt.style.use('dark_background')

# EClient allows us to request data from the server
# EWrapper is the place to recieve the data
class LiveSurfaceApp(EClient, EWrapper):

    def __init__(self):
        EClient.__init__(self, self)
        self.iv_dict = {} # based on requestID. create IV req from server, each ID maps to a vol
        self.id_map = {} # reqID -> (strikePrice, Expr)
        self.expirations = []
        self.strikes = []
        self.spot_price = 0
        self.underlying_conId = 0
        self.resolved = threading.Event()
        self.chain_resolved = threading.Event()

    def connectAck(self):
        print("TWS Acknowledged Connection")

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            print(reqId, errorCode, errorString)

    def contractDetails(self, reqId, contractDetails):
        self.underlying_conId = contractDetails.contract.conId
        self.resolved.set()

    def tickPrice(self, reqId, tickType, price, attrib):
        if reqId == 999 and tickType in [4, 9] and price > 0:
            self.spot_price = price

    def securityDefinitionOptionParameter(self, reqId, exchange, underlyingConId,tradingclass, multiplier, expirations, strikes):
        if exchange == "SMART":
            self.expirations = sorted(list(expirations))
            self.strikes = sorted(list(strikes))
            self.chain_resolved.set()

    def tickOptionComputation(self, reqId, tickType, tickAttrib, impledVol, delta, optPrice, pvDividend, gamma, vega, theta, underlyingPrice):
        if tickType == 13 and impledVol is not None:
            self.iv_dict[reqId] = impledVol
            
