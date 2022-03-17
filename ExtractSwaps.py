
"""
Cyclic arbitrage on UniSwapV2:
    0x0ddb5fc93c9ebdf948c18e61f422eb0167d8ef84d0648e20361ab40526c07789


"""

import pprint
import requests
import json
import os
import traceback
from threading import Thread


MY_API_KEYS = [
    "KEY1", ## Fill your keys here
    "KEY2", 
    "KEY3"
]

FACTORY_ADDRESS = {
    "uniswapv3" : "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    "uniswapv2" : "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
    "sushiswap" : "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac"
}
FACTORY_POOLCREATED_EVENT = {
    "uniswapv3" : "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118",
    "uniswapv2" : "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
    "sushiswap" : "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"
}
POOL_SWAP_EVENT = {
    "uniswapv3" : "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67",
    "uniswapv2" : "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822",
    "sushiswap" : "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
}
FACTORY_POOLCREATED_EVENT_CONTRACT = {
    "uniswapv3" : lambda x: "0x" + x["data"][-40:],
    "uniswapv2" : lambda x: "0x" + x["data"][26:66],
    "sushiswap" : lambda x: "0x" + x["data"][26:66]
}

def from_UniSwapV3(token0, token1, x):
    amount0 = getSigned(getInt("0x" + x["data"][2:2+64]))
    amount1 = getSigned(getInt("0x" + x["data"][2+64:2+2*64]))
    if ((amount0 > 0) == (amount1 > 0)):
        print(f"Something wrong with {x}")
        return (-1, token0 + token1)
    if (amount0 > 0):
        return (amount0, token0)
    elif (amount1 > 0):
        return (amount1, token1)
    else:
        assert (0), f"Something wrong with {x}"

def to_UniSwapV3(token0, token1, x):
    amount0 = getSigned(getInt("0x" + x["data"][2:2+64]))
    amount1 = getSigned(getInt("0x" + x["data"][2+64:2+2*64]))
    if ((amount0 < 0) == (amount1 < 0)):
        print(f"Something wrong with {x}")
        return (-1, token0 + token1)
    if (amount0 < 0):
        return (-1 * amount0, token0)
    elif (amount1 < 0):
        return (-1 * amount1, token1)
    else:
        assert (0), f"Something wrong with {x}"

def from_UniSwapV2(token0, token1, x):
    amount0In = getInt("0x" + x["data"][2:2+64])
    amount1In = getInt("0x" + x["data"][2+64:2+64*2])
    amount0Out = getInt("0x" + x["data"][2+64*2:2+64*3])
    amount1Out = getInt("0x" + x["data"][2+64*3:2+64*4])
    amount0 = amount0In - amount0Out
    amount1 = amount1In - amount1Out
    if ((amount0 > 0) == (amount1 > 0)):
        print(f"Something is wrong with {x}")
        return (-1, token0 + token1)
    if (amount0 > 0):
        return (amount0, token0)
    elif (amount1 > 0):
        return (amount1, token1)
    else:
        assert (0), f"Something wrong with {x}"


def to_UniSwapV2(token0, token1, x):
    amount0In = getInt("0x" + x["data"][2:2+64])
    amount1In = getInt("0x" + x["data"][2+64:2+64*2])
    amount0Out = getInt("0x" + x["data"][2+64*2:2+64*3])
    amount1Out = getInt("0x" + x["data"][2+64*3:2+64*4])
    amount0 = amount0In - amount0Out
    amount1 = amount1In - amount1Out
    if ((amount0 < 0) == (amount1 < 0)):
        print(f"Something wrong with {x}")
        return (-1, token0 + token1)
    if (amount0 < 0):
        return (-1 * amount0, token0)
    elif (amount1 < 0):
        return (-1 * amount1, token1)
    else:
        assert (0), f"Something wrong with {x}"



POOL_SWAP_FROM = {
    "uniswapv3" : from_UniSwapV3,
    "uniswapv2" : from_UniSwapV2,
    "sushiswap" : from_UniSwapV2
}
POOL_SWAP_TO = {
    "uniswapv3" : to_UniSwapV3,
    "uniswapv2" : to_UniSwapV2,
    "sushiswap" : to_UniSwapV2
}

## ## For specific Arbitrage Transaction
## SWAPS_START_BLOCK = 14035430
## SWAPS_END_BLOCK   = 14035430

SWAPS_START_BLOCK = 14020000
SWAPS_END_BLOCK   = 14050000

HISTORY_END_BLOCK = SWAPS_END_BLOCK

def getSigned(value):
    return -(value & 0x8000000000000000000000000000000000000000000000000000000000000000) | \
            (value & 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)

def getInt(value):
    if value != "0x":
        return int(value, 16)
    return 0

def getCreatedPools(dex, fromBlock, toBlock, keyIdx):
    print(f"{dex}: fromBlock = {fromBlock}, toBlock = {toBlock}")
    try:
        r = requests.get(
            f"https://api.etherscan.io/api",
            params = {
                "module" : "logs",
                "action" : "getLogs",
                "address" : FACTORY_ADDRESS[dex],
                "topic0" : FACTORY_POOLCREATED_EVENT[dex],
                "fromBlock" : fromBlock,
                "toBlock" : toBlock,
                "apikey" : MY_API_KEYS[keyIdx]
            }
        ).json()
        assert(r["message"] == "OK")
        r = r["result"]
        r = [ { "blockNumber" : getInt(x["blockNumber"]), 
                "token0" : "0x" + x["topics"][1][-40:],
                "token1" : "0x" + x["topics"][2][-40:],
                "poolContract" : FACTORY_POOLCREATED_EVENT_CONTRACT[dex](x)
                } for x in r]
        r = { x["poolContract"] : x for x in r }
        return r
    except:
        print(f"{dex}: FAILED getting pools from {fromBlock} to {toBlock}")
        traceback.print_exc()
        pprint.pprint(r)
        exit(-1)


def getPools(dex, keyIdx):
    print(f"{dex}: Getting pools")
    try:
        with open(f'data/{dex}_pools.json', 'r') as json_file:
            return json.load(json_file)
    except:
        print(f"{dex}: Can't load pools from existing file")

    allPools = dict()
    startBlock = 0
    endBlock = HISTORY_END_BLOCK
    while True:
        curr = getCreatedPools(dex, startBlock, endBlock, keyIdx)
        prevNum = len(allPools)
        allPools.update(curr)
        afterNum = len(allPools)
        print(f"{dex}: prevNum = {prevNum}, afterNum = {afterNum}")
        if (prevNum == afterNum):
            break
        else:
            startBlock = max(x["blockNumber"] for x in curr.values())
            
    allPools = list(allPools.values())
    with open(f'data/{dex}_pools.json', 'w') as json_file:
        json.dump(allPools, json_file, indent=4)

    return allPools


def getTokensFromPools(dex, pools):
    try:
        with open(f'data/{dex}_tokens.json', 'r') as json_file:
            return json.load(json_file)
    except:
        print(f"{dex}: Can't load tokens from existing file for")
    tokens = list(set([x[s] for s in ["token0", "token1"] for x in pools]))
    with open(f'data/{dex}_tokens.json', 'w') as json_file:
        json.dump(tokens, json_file, indent=4)
    return tokens
    

def getSwapsFromPoolForBlocks(dex, poolAddress, token0, token1, fromBlock, toBlock, keyIdx):
    print(f"{dex}: pool = {poolAddress}, fromBlock = {fromBlock}, toBlock = {toBlock}")
    try:
        r = requests.get(
                f"https://api.etherscan.io/api",
                params = {
                    "module" : "logs",
                    "action" : "getLogs",
                    "address" : poolAddress,
                    "topic0" : POOL_SWAP_EVENT[dex],
                    "fromBlock" : fromBlock,
                    "toBlock" : toBlock,
                    "apikey" : MY_API_KEYS[keyIdx]
                }
            ).json()
        assert(r["message"] == "OK" or r["message"] == "No records found")
        r = r["result"]
        r = [ { "blockNumber" : getInt(x["blockNumber"]), 
                "transactionIndex" : getInt(x["transactionIndex"]), 
                "logIndex" : getInt(x["logIndex"]),
                "transactionHash" : x["transactionHash"],
                "sender" : "0x" + x["topics"][1][-40:],
                "recipient" : "0x" + x["topics"][2][-40:],
                "timeStamp" : x["timeStamp"],
                "gasPrice" : x["gasPrice"],
                "gasUsed" : x["gasUsed"],
                "from" : POOL_SWAP_FROM[dex](token0, token1, x),
                "to" : POOL_SWAP_TO[dex](token0, token1, x),
                } for x in r]
        r = { f'{x["blockNumber"]}-{x["transactionIndex"]}-{x["logIndex"]}' : x for x in r }
        return r
    except:
        print(f"{dex}: FAILED getting swaps for {poolAddress} from {fromBlock} to {toBlock}")
        traceback.print_exc()
        pprint.pprint(r)


def getSwapsFromPool(dex, poolAddress, token0, token1, keyIdx):
    while True:
        try:
            try:
                with open(f'data/{dex}_swaps/{poolAddress}.json', 'r') as json_file:
                    return json.load(json_file)
            except:
                print(f"{dex}: Can't load swaps for {poolAddress} from existing file")

            allSwaps = dict()
            startBlock = SWAPS_START_BLOCK
            endBlock =  SWAPS_END_BLOCK
            while True:
                curr = getSwapsFromPoolForBlocks(dex, poolAddress, token0, token1, startBlock, endBlock, keyIdx)
                prevNum = len(allSwaps)
                allSwaps.update(curr)
                afterNum = len(allSwaps)
                print(f"{dex}: prevNum = {prevNum}, afterNum = {afterNum}")
                if (prevNum == afterNum):
                    break
                else:
                    startBlock = max(x["blockNumber"] for x in curr.values())
                    
            allSwaps = list(allSwaps.values())
            with open(f'data/{dex}_swaps/{poolAddress}.json', 'w') as json_file:
                json.dump(allSwaps, json_file, indent=4)

            return allSwaps
        except:
            print(f"{dex}: FAILED getting swaps for {poolAddress}. Will retry..")


## ## For specific Arbitrage Transaction
## SPECIAL_POOLS = [
##     "0x69b81152c5a8d35a67b32a4d3772795d96cae4da",
##     "0x69061b8a0214a8d10145d8471730151434ca54ff",
##     "0xc218001e3d102e3d1de9bf2c0f7d9626d76c6f30",
##     "0xe3a16a005d0ce69059f4017cd8bf990ccc717606",
##     "0x7ce01885a13c652241ae02ea7369ee8d466802eb"
## ]

def extractData(dex, keyIdx, results):
    os.makedirs(f"data/{dex}_swaps", exist_ok=True)
    print(f"{dex}: Extracting data")
    pools = getPools(dex, keyIdx)
    print(f"{dex}: Num Pools is {len(pools)}")
    tokens = getTokensFromPools(dex, pools)
    print(f"{dex}: Num Tokens is {len(tokens)}")
    swaps = dict()
    for pool in pools:
        poolAddress = pool["poolContract"]
        ## ## For specific Arbitrage Transaction
        ## if not poolAddress in SPECIAL_POOLS:
        ##     continue
        swaps[poolAddress] = getSwapsFromPool(dex, poolAddress, pool["token0"], pool["token1"], keyIdx)
        print(f"{dex}: Num Swaps for {poolAddress} is {len(swaps[poolAddress])}")
    results.append((dex, swaps))

def createSwapsHistory(allSwaps):
    ret = dict()
    for dex, swaps in allSwaps:
        for poolAddress in swaps:
            for swap in swaps[poolAddress]:
                swap["dex"] = dex
                swap["poolAddress"] = poolAddress
                ## Add to dict
                if (swap["blockNumber"] not in ret):
                    ret[swap["blockNumber"]] = dict()
                if (swap["transactionIndex"] not in ret[swap["blockNumber"]]):
                    ret[swap["blockNumber"]][swap["transactionIndex"]] = []
                ret[swap["blockNumber"]][swap["transactionIndex"]].append(swap)
                ret[swap["blockNumber"]][swap["transactionIndex"]].sort(key=lambda x:x["logIndex"])
    with open(f'data/swap_history.json', 'w') as json_file:
        json.dump(ret, json_file, indent=4)
    return ret



def main():
    os.makedirs("data", exist_ok=True)
    dexes = ["uniswapv3", "uniswapv2", "sushiswap"]
    results = []
    threads = []
    for i, dex in enumerate(dexes):
        thread = Thread(target = extractData, args = (dex, i, results, ))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    createSwapsHistory(results)

if __name__=='__main__':
    main()


