import ccxt.async_support as ccxt
import pandas as pd
from typing import List
from pydantic import BaseModel
import asyncio

class Position(BaseModel):
    pair: str
    side: str
    size: float
    usd_size: float
    entry_price: float
    leverage: float

class PerpMexc:
    def __init__(self, public_api, secret_api):
        self._session = ccxt.mexc({
            "apiKey": public_api,
            "secret": secret_api,
            "enableRateLimit": True,
            "options": {"defaultType": "future"}
        })

    async def load_markets(self):
        await self._session.load_markets()

    async def close(self):
        await self._session.close()

    async def get_balance(self):
        try:
            bal = await self._session.fetch_balance({'type': 'future'})
            return bal['USDT']['total']
        except: return 0.0

    async def set_leverage(self, pair, leverage):
        try:
            await self._session.set_leverage(leverage, pair)
            await self._session.set_margin_mode('isolated', pair) # Isolated par sécurité
        except: pass

    async def get_last_ohlcv(self, pair, tf, limit=100):
        ohlcv = await self._session.fetch_ohlcv(pair, tf, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["date", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["date"], unit="ms")
        df.set_index("date", inplace=True)
        return df

    async def get_open_positions(self, pairs):
        # MEXC retourne tout, on filtre
        try:
            raw = await self._session.fetch_positions()
            res = []
            for p in raw:
                if p['symbol'] in pairs and float(p['contracts']) > 0:
                    res.append(Position(
                        pair=p['symbol'],
                        side=p['side'], # long/short
                        size=float(p['contracts']),
                        usd_size=float(p['notional']),
                        entry_price=float(p['entryPrice']),
                        leverage=float(p['leverage'])
                    ))
            return res
        except: return []

    async def cancel_all_orders(self, pair):
        try: await self._session.cancel_all_orders(pair)
        except: pass

    async def place_order(self, pair, side, price, size, reduce=False):
        params = {}
        if reduce: params['reduceOnly'] = True
        try:
            await self._session.create_order(pair, 'limit', side, size, price, params)
        except Exception as e: print(f"Order error {pair}: {e}")

    async def place_trigger_order(self, pair, side, trigger_price, size, reduce=False):
        # Stop Loss Market
        params = {'triggerPrice': trigger_price}
        if reduce: params['reduceOnly'] = True
        try:
            # MEXC utilise souvent 'stop-market' via params ou create_order
            # Adaptation simple pour CCXT/MEXC:
            await self._session.create_order(pair, 'market', side, size, params=params)
        except: pass
        
    def price_to_precision(self, pair, price):
        return float(self._session.price_to_precision(pair, price))

    def amount_to_precision(self, pair, amount):
        return float(self._session.amount_to_precision(pair, amount))
