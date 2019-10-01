import websockets
import asyncio
import pandas as pd
import logging
import json

logger = logging.getLogger()


class Clock:
    def __init__(self, base_time):
        self._base_time = pd.Timestamp(base_time, tz='America/New_York')
        self._start_time = pd.Timestamp.now(tz='America/New_York')

    def now(self):
        real = pd.Timestamp.now(tz='America/New_York')
        return self._base_time + (real - self._start_time)


def main():
    symbol = 'AAPL'
    df = pd.read_csv('data/trades/AAPL.csv')
    df.timestamp = pd.to_datetime(df.timestamp)
    clock = Clock('2019-09-27 09:30')

    async def handler(websocket, path):

        await websocket.send('[{"ev":"status","status":"connected","message":"Connected Successfully"}]')
        auth_msg = await websocket.recv()
        logger.info(f'auth_msg = {auth_msg}')
        await websocket.send('{"action":"auth","params":"*******"}')
        subscribe = await websocket.recv()
        logger.info(f'subscribe = {subscribe}')
        await websocket.send('[{"ev":"status","status":"success","message":"subscribed to: T.MSFT"}]')

        cursor = df.timestamp[df.timestamp < clock._base_time].index[-1]
        while True:
            now = clock.now()
            tillnow = df.timestamp[df.timestamp < now].index[-1]
            for i in range(cursor + 1, tillnow + 1):
                row = df.iloc[i]
                await websocket.send(json.dumps({
                    "ev": "T",
                    "sym": symbol,
                    "x": str(row.exchange),
                    "i": i,
                    "z": 1,
                    "p": row.price,
                    "s": row.size,
                    "c": [int(c) for c in [
                        row.condition1,
                        row.condition2,
                        row.condition3,
                        row.condition4] if c != 0],
                    "t": row.timestamp.value // 10**6,
                }))
            cursor = tillnow
            if cursor > len(df):
                break
            await asyncio.sleep(0.01)

    logger.info('starting server...')
    start_server = websockets.serve(handler, 'localhost', 6999)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
