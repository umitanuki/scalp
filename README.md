# Concurrent Scalp Algo

This python script is a working example to execute scalping trading algorithm for
[Alpaca API](https://alpaca.markets). This algorithm uses real time order updates
as well as minute level bar streaming from Polygon via Websockets.
One of the contributions of this example is to demonstrate how to handle
multiple stocks concurrently as independent routine using Python's asyncio.

The strategy holds positions up to 2 minute and exits positions quickly, so
you have to have more than $25k equity in your account due to the Pattern Day Trader rule,
to run this example.

## Dependency
This script needs latest (Alpaca Python SDK)[https://github.com/alpacahq/alpaca-trade-api-python].
Please install it using pip

```sh
$ pip3 install alpaca-trade-api
```

or use pipenv using `Pipfile` in this directory.

```sh
$ pipenv install
```

## How to Run

```sh
$ python main.py --lot=2000 SPY
```


## Strategy
The algorithm idea is to buy the stock upon the buy signal (MA20/price cross over in 1 minute) as
much as `lot` amount of dollar, then immediately sell the position at or above the entry price.
The buy signal is expremely simple, but what this strategy achieves is the quick reaction to
exit the position as soon as the buy order fills. There are reasonable chances that you can sell
the positions at the better prices than your entry within the short period of time. We send
limit order at the last trade or entry price whichever the higher to avoid unnecessary slippage.

If the strategy fails to exit the position, it automatically bails out buy submitting market order
to force liquidation after 2 minutes. Depending on the situation, this may cause loss more than
the accumulated profit, and this is where you can improve the risk control beyond this example.

The buy signal is calculated as soon as a minute bar arrives, which typically happen about 4 seconds
after the top of every minute (this is Polygon's behavior for minute bar streaming).

This example liquidates all watching positions with market order at the end of market hours (03:55pm ET).


## Implementation
This example heavily relies on Python's asyncio. Although the thread is single, we can handle
multiple symbols concurrently thanks to this async loop.