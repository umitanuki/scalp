import alpaca_trade_api as alpaca
# import numpy as np
import pandas as pd
import time
import asyncio

import logging

logger = logging.getLogger()


class Algo:

    def __init__(self, api, symbol):
        self._api = api
        self._symbol = symbol
        self._bars = []

        now = pd.Timestamp.now(tz='America/New_York').floor('1min')
        market_open = now.replace(hour=9, minute=30)
        today = now.strftime('%Y-%m-%d')
        tomorrow = (now + pd.Timedelta('1day')).strftime('%Y-%m-%d')
        data = api.polygon.historic_agg_v2(
            symbol, 1, 'minute', today, tomorrow, unadjusted=False).df
        bars = data[market_open:]
        self._bars = bars

        self._order = None
        self._position = None
        self._state = 'TO_BUY'
        self._l = logger.getChild(self._symbol)

    def check_state(self, position):
        # self._l.info('periodic task')
        if self._state == 'BUY_SUBMITTED':
            if position:
                # order filled
                self._position = position
                self._transition('TO_SELL')
                self._submit_sell()
        elif self._state == 'SELL_SUBMITTED':
            order = self._api.get_order(self._order.id)
            if order.status == 'filled':
                self._order = None
                self._position = None
                self._transition('TO_BUY')
            elif order.status in ('canceled', 'rejected'):
                self._order = None
                self._transition('TO_SELL')

    def on_bar(self, bar):
        self._bars = self._bars.append(pd.DataFrame({
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
        }, index=[bar.start]))

        self._l.info(
            f'received bar start = {bar.start}, close = {bar.close}, len(bars) = {len(self._bars)}')
        if len(self._bars) < 21:
            return
        if self._state == 'TO_BUY':
            mavg = self._bars.rolling(20).mean().close.values
            closes = self._bars.close.values
            if closes[-2] < mavg[-2] and closes[-1] > mavg[-1]:
                self._l.info(
                    f'buy signal: closes[-2] {closes[-2]} < mavg[-2] {mavg[-2]} '
                    f'closes[-1] {closes[-1]} > mavg[-1] {mavg[-1]}')
                self._submit_buy()
            else:
                self._l.info(
                    f'closes[-2:] = {closes[-2:]}, mavg[-2:] = {mavg[-2:]}')

    def on_order_update(self, event, order):
        self._l.info(f'order update: {event} = {order}')
        if event == 'fill':
            self._order = None
            if self._state == 'BUY_SUBMITTED':
                self._position = self._api.get_position(self._symbol)
                self._transition('TO_SELL')
                self._submit_sell()
                return
            elif self._state == 'SELL_SUBMITTED':
                self._position = None
                self._transition('TO_BUY')
                return
        elif event == 'partial_fill':
            self._position = self._api.get_position(self._symbol)
            self._order = self._api.get_order(order['id'])
            return
        elif event == 'canceled' or 'rejected':
            if event == 'rejected':
                self._l.warn(f'order rejected: current order = {self._order}')
            self._order = None
            if self._state == 'BUY_SUBMITTED':
                if self._position is not None:
                    self._transition('TO_SELL')
                    self._submit_sell()
                else:
                    self._transition('TO_BUY')
            elif self._state == 'SELL_SUBMITTED':
                self._transition('TO_SELL')
                self._submit_sell()
            else:
                self._l.warn(f'unexpected state for {event}: {self._state}')
        elif event == 'new':
            o = self._api.get_order(order['id'])
            time.sleep(0.5)
            if o.status == 'filled':
                self.on_order_update('fill', order)

    def _submit_buy(self):
        trade = self._api.polygon.last_trade(self._symbol)
        amount = int(5000 / trade.price)
        try:
            order = self._api.submit_order(
                symbol=self._symbol,
                side='buy',
                type='limit',
                qty=amount,
                time_in_force='day',
                limit_price=trade.price,
            )
        except Exception as e:
            self._l.info(e)
            self._transition('TO_BUY')
            return

        self._order = order
        self._l.info(f'submitted buy {order}')
        self._transition('BUY_SUBMITTED')

    def _submit_sell(self):
        current_price = float(self._api.polygon.last_trade(self._symbol).price)
        cost_basis = float(self._position.avg_entry_price)
        limit_price = cost_basis + 0.01
        if current_price > limit_price:
            limit_price = current_price
        try:
            order = self._api.submit_order(
                symbol=self._symbol,
                side='sell',
                type='limit',
                qty=self._position.qty,
                time_in_force='day',
                limit_price=limit_price,
            )
            self._l.info(f'submitted sell {order}')
        except Exception as e:
            self._l.error(e)
            self._transition('TO_SELL')
            return

        self._order = order
        self._transition('SELL_SUBMITTED')

    def _transition(self, new_state):
        self._l.info(f'transition from {self._state} to {new_state}')
        self._state = new_state


def main(args):
    api = alpaca.REST()
    stream = alpaca.StreamConn()

    fleet = {}
    symbols = args.symbols
    for symbol in symbols:
        algo = Algo(api, symbol)
        fleet[symbol] = algo

    @stream.on(r'^AM')
    async def on_bars(conn, channel, data):
        # append to bar list
        # calculate MA20
        # MA cross over, buy alotted amount with limit=last_trade
        # wait for 30 seconds, cancel if not filled.
        # if filled, set limit sell at next cent.
        #
        if data.symbol in fleet:
            fleet[data.symbol].on_bar(data)

    @stream.on(r'^T$')
    async def on_trades(conn, channel, data):
        pass

    @stream.on(r'trade_updates')
    async def on_trade_updates(conn, channel, data):
        logger.info(f'trade_updates {data}')
        symbol = data.order['symbol']
        if symbol in fleet:
            fleet[symbol].on_order_update(data)

    async def periodic():
        while True:
            await asyncio.sleep(1)
            positions = api.list_positions()
            for symbol, algo in fleet.items():
                pos = [p for p in positions if p.symbol == symbol]
                algo.check_state(pos[0] if len(pos) > 0 else None)
    channels = ['trade_updates'] + [
        'AM.' + symbol for symbol in symbols
    ]

    # stream.run(channels)
    loop = stream.loop
    loop.run_until_complete(asyncio.gather(
        stream.subscribe(channels),
        periodic(),
    ))
    loop.close()


if __name__ == '__main__':
    import argparse

    fmt = '%(asctime)s:%(filename)s:%(lineno)d:%(levelname)s:%(message)s'
    logging.basicConfig(level=logging.INFO, format=fmt)
    fh = logging.FileHandler('console.log')
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(fmt))
    logger.addHandler(fh)

    parser = argparse.ArgumentParser()
    parser.add_argument('symbols', nargs='+')

    main(parser.parse_args())
