import sys
import os
import asyncio
import ta
import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utilities.mexc_perp import PerpMexc
from secret import ACCOUNTS

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    print(f"--- Execution {datetime.datetime.now()} ---")
    account = ACCOUNTS["mexc1"]
    leverage = 2.35
    tf = "1h"
    sl = 0.32
    
    # 20 Paires Optimisées (Format MEXC: BTC/USDT:USDT)
    params = {
        "BTC/USDT:USDT": {"ma": 4, "env": [0.070, 0.110, 0.120, 0.150, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "ETH/USDT:USDT": {"ma": 2, "env": [0.090, 0.140, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "ADA/USDT:USDT": {"ma": 4, "env": [0.020, 0.080, 0.090], "size": 0.1, "sides": ["long", "short"]},
        "AVAX/USDT:USDT": {"ma": 3, "env": [0.050, 0.060, 0.070, 0.200, 0.250], "size": 0.1, "sides": ["long", "short"]},
        "EGLD/USDT:USDT": {"ma": 8, "env": [0.080, 0.120, 0.160, 0.170, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "KSM/USDT:USDT": {"ma": 5, "env": [0.070, 0.110, 0.120, 0.150, 0.230], "size": 0.1, "sides": ["long", "short"]},
        "OCEAN/USDT:USDT": {"ma": 6, "env": [0.040, 0.150, 0.180, 0.200, 0.220], "size": 0.1, "sides": ["long", "short"]},
        "ACH/USDT:USDT": {"ma": 7, "env": [0.040, 0.130, 0.140, 0.150, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "APE/USDT:USDT": {"ma": 4, "env": [0.070, 0.100, 0.120, 0.150, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "CRV/USDT:USDT": {"ma": 5, "env": [0.040, 0.050, 0.100], "size": 0.1, "sides": ["long", "short"]},
        "DOGE/USDT:USDT": {"ma": 3, "env": [0.080, 0.110, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "ENJ/USDT:USDT": {"ma": 3, "env": [0.120, 0.150, 0.200, 0.220, 0.300], "size": 0.1, "sides": ["long", "short"]},
        "FET/USDT:USDT": {"ma": 2, "env": [0.040, 0.150, 0.170, 0.190, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "ICP/USDT:USDT": {"ma": 4, "env": [0.090, 0.110, 0.140, 0.150, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "IMX/USDT:USDT": {"ma": 3, "env": [0.080, 0.100, 0.130, 0.180, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "LDO/USDT:USDT": {"ma": 2, "env": [0.100, 0.130, 0.150, 0.190, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "MAGIC/USDT:USDT": {"ma": 8, "env": [0.110, 0.150, 0.200, 0.250, 0.280], "size": 0.1, "sides": ["long", "short"]},
        "SAND/USDT:USDT": {"ma": 3, "env": [0.050, 0.070, 0.100, 0.250, 0.300], "size": 0.1, "sides": ["long", "short"]},
        "TRX/USDT:USDT": {"ma": 8, "env": [0.050, 0.070, 0.100, 0.150, 0.200], "size": 0.1, "sides": ["long", "short"]},
        "XTZ/USDT:USDT": {"ma": 8, "env": [0.100, 0.130, 0.200, 0.240, 0.260], "size": 0.1, "sides": ["long", "short"]}
    }

    exchange = PerpMexc(account["public_api"], account["secret_api"])
    await exchange.load_markets()
    pairs = list(params.keys())
    invert = {"long": "sell", "short": "buy"}

    print("Setup...")
    await asyncio.gather(*[exchange.set_leverage(p, leverage) for p in pairs])

    print("Data...")
    dfs = await asyncio.gather(*[exchange.get_last_ohlcv(p, tf, 100) for p in pairs])
    df_map = dict(zip(pairs, dfs))

    for p, df in df_map.items():
        conf = params[p]
        df["ma"] = ta.trend.sma_indicator(df["close"], window=conf["ma"])
        for i, e in enumerate(conf["env"]):
            df[f"up_{i+1}"] = df["ma"] * (1 + e)
            df[f"dn_{i+1}"] = df["ma"] * (1 - e)
        df_map[p] = df

    bal = await exchange.get_balance()
    print(f"Balance: {bal:.2f} USDT")
    
    print("Cleaning Orders...")
    await asyncio.gather(*[exchange.cancel_all_orders(p) for p in pairs])

    print("Positions...")
    positions = await exchange.get_open_positions(pairs)
    tasks = []

    for pos in positions:
        print(f"Pos: {pos.pair} {pos.side} ({pos.usd_size}$)")
        row = df_map[pos.pair].iloc[-1]
        
        # TP
        tp_side = invert[pos.side]
        tasks.append(exchange.place_order(pos.pair, tp_side, row["ma"], pos.size, reduce=True))
        
        # SL
        sl_px = pos.entry_price * (1 - sl) if pos.side == "long" else pos.entry_price * (1 + sl)
        tasks.append(exchange.place_trigger_order(pos.pair, tp_side, sl_px, pos.size, reduce=True))
        
        # DCA
        conf = params[pos.pair]
        total = len(conf["env"])
        alloc = (conf["size"] * bal * leverage) / total
        layer = min(int(pos.usd_size / alloc), total)
        
        for i in range(layer, total):
            idx = i + 1
            if pos.side == "long":
                px = row[f"dn_{idx}"]
                sz = alloc / px
                tasks.append(exchange.place_order(pos.pair, "buy", px, sz))
            else:
                px = row[f"up_{idx}"]
                sz = alloc / px
                tasks.append(exchange.place_order(pos.pair, "sell", px, sz))

    # New Entries
    pos_sym = [p.pair for p in positions]
    for p in pairs:
        if p in pos_sym: continue
        row = df_map[p].iloc[-1]
        conf = params[p]
        total = len(conf["env"])
        alloc = (conf["size"] * bal * leverage) / total
        
        if alloc < 5: continue # Min order size security

        for i in range(total):
            idx = i + 1
            if "long" in conf["sides"]:
                px = row[f"dn_{idx}"]
                sz = alloc / px
                tasks.append(exchange.place_order(p, "buy", px, sz))
            if "short" in conf["sides"]:
                px = row[f"up_{idx}"]
                sz = alloc / px
                tasks.append(exchange.place_order(p, "sell", px, sz))

    if tasks: 
        print(f"Placing {len(tasks)} orders...")
        await asyncio.gather(*tasks)
    
    await exchange.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
