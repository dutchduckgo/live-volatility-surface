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
        self.iv_dict = {} # reqId -> impledVol. based on requestID. create IV req from server, each ID maps to a vol
        self.id_map = {} # reqId -> (strikePrice, Expr)
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

    def securityDefinitionOptionParameter(self, reqId, exchange, underlyingConId, tradingclass, multiplier, expirations, strikes):
        if exchange == "SMART":
            self.expirations = sorted(list(expirations))
            self.strikes = sorted(list(strikes))
            self.chain_resolved.set()

    def tickOptionComputation(self, reqId, tickType, tickAttrib, impledVol, delta, optPrice, pvDividend, gamma, vega, theta, underlyingPrice):
        if tickType == 13 and impledVol is not None:
            self.iv_dict[reqId] = impledVol

    def run_loop(app):
        app.run()

    def start_app(symbol="SPY"):
        app = LiveSurfaceApp()
        app.connect('127.0.0.1', 7497, clientId=35) #clientId random number?

        api_thread = threading.Thread(target=run_loop, args={app,}, daemon=True)
        api_thread.start()
        time.sleep(1)

        underlying = Contract()
        underlying.symbol = symbol
        underlying.secType = 'STK'
        underlying.exchange = 'SMART'
        underlying.currency = 'USD'

        app.reqContractDetails(1, underlying) # reqId = 1, request contractId
        app.resolve.wait(timeout=5)

        app.reqMktData(999, underlying, "", False, False, []) # reqId = 999, request data for underlying contract
        while app.spot_price == 0: # wait until spot price recieved
            time.sleep(.1)

        spot = app.spot_price

        app.reqSecDefOptParams(2, symbol, "", "STK", app.underlying_conId)
        app.chain_resolved.wait(timeout=5) 
        # notice in both reqContractDetails and here, we set threading event to wait. 
        # when server response, we set it and we have pass-through so we continue with the program

        today = time.strftime("%Y%m%d")
        target_exps = [e for e in app.expirations if e >= today][:6] # filter all exprs by today, ensure we dont have expr for yesterday
        target_strikes = [s for s in app.strikes if spot * .98 <= s <= spot * 1.02] # pull strikes around the money

        req_id = 1000
        for exp in target_exps:
            for strike in target_strikes:
                opt = Contract()
                opt.symbol = symbol
                opt.secType = 'OPT'
                opt.exchange = 'SMART'
                opt.currency = 'USD'
                opt.lastTradeDateOrContractMonth = exp
                opt.strike = strike
                opt.right = 'C' if strike >= spot else 'P'
                app.id_map[req_id] = (exp, strike)

                # tickType 106 = IV
                app.reqMktData(req_id, opt, "106", False, False, [])
                req_id += 1
                time.sleep(.1)

        return app

class PlotState:

    def __init__(self):
        self.is_locked = False

    def toggle(self, event):
        self.is_locked = not self.is_locked
        btn_label.set_text("UNLOCK UPDATES" if self.is_locked else "LOCK UPDATES")
        plt.draw()

    def live_desktop_plot(app):
        plt.ion()
        fig = plt.figure(figsize=(16, 9))
        fig.canvas.manager.set_window_title("Life Volalility Surface")
        fig.patch.set_facecolor("#0b0d0f")

        ax_3d = plt.subplot2grid((1, 3), (0, 0), colspan=2, projection='3d')
        ax_skew = plt.subplot2grid((1, 3), (0, 2))

        state = PlotState()
        ax_button = plt.axes([.42, .03, .12, .04])
        global btn_label
        btn = Button(ax_button, "LOCK UPDATES", color='#1f2329', hovercolor="#2d333b")
        btn_label = btn_label
        btn_label.set_color('white')
        btn_label.set_fontsize(9)
        btn.on_clicked(state.toggle)

        print(" --- Live Implied Volatility Surface Started --- ")
        

    