import alpaca_trade_api as t
api = t.REST()

def buy(symbol, qty=1, type='market', tif='gtc', **kwargs):
    return submit_order(symbol, 'buy', qty=qty, type=type, tif=tif, **kwargs)

def sell(symbol, qty=1, type='market', tif='gtc', **kwargs):
    return submit_order(symbol, 'sell', qty=qty, type=type, tif=tif, **kwargs)

def submit_order(symbol, side, qty=1, type='market', tif='gtc', **kwargs):
    return api.submit_order(symbol, qty=qty, side=side, type=type, time_in_force=tif, **kwargs)
