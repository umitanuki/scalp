import alpaca_trade_api as alpaca
import pandas as pd
import logging
import os

logger = logging.getLogger()

api = alpaca.REST()

def get_quotes(symbol, start, end):
    return get_trades_or_quotes(api.polygon.historic_quotes, symbol, start, end)


def get_trades(symbol, start, end):
    return get_trades_or_quotes(api.polygon.historic_trades, symbol, start, end)


def get_trades_or_quotes(api_call, symbol, start, end):
    start = pd.Timestamp(start, tz='America/New_York')
    end = pd.Timestamp(end, tz='America/New_York')
    total = None
    current = start
    while True:
        logger.info(current)
        try:
            resp = api_call(
                symbol,
                current.strftime('%Y-%m-%d'),
                offset=current.value // 10**6,
                limit=50000,
            )
        except TypeError:
            break
        df = resp.df
        if len(df) == 0:
            current = (current + pd.Timedelta('24 hours')).floor('1D')
            if current > end:
                break
        if total is None:
            total = df
        else:
            total = total.append(df)
        current = df.index[-1]
    return total

def main(args):

    trades = get_trades(args.symbol, args.start, args.end)
    filename = f'./data/trades/{args.symbol}.csv'
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    trades.to_csv(filename)
    logger.info(f'{args.symbol} trades = {trades.shape} to {filename}')
    quotes = get_quotes(args.symbol, args.start, args.end)
    filename = f'./data/quotes/{args.symbol}.csv'
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    quotes.to_csv(filename)
    logger.info(f'{args.symbol} quotes = {quotes.shape} to {filename}')

if __name__ == '__main__':
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('symbol')
    parser.add_argument('start')
    parser.add_argument('end', default=pd.Timestamp.now(tz='America/New_York').strftime('%Y-%m-%d'))

    main(parser.parse_args())