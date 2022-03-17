
import json
import pprint
import itertools
import functools


def loadSwapHistory():
    try:
        with open(f'data/swap_history.json', 'r') as json_file:
            return json.load(json_file)
    except:
        print(f"Couldn't load Swaps!!")
        exit(-1)


def isCycleClosed(currList):
    return currList[-1]["to"][1] == currList[0]["from"][1]


MAX_CROSS_TRANSACTION = 5
ADDRESSES_KEYS = ["sender", "recipient"]
ADDRESSES_KEYS_AND_POOL = ["sender", "recipient", "poolAddress"]


def canExtend(swapL, swapR):
    return (swapL["to"][1] == swapR["from"][1]) and \
           (swapL["to"][0] >= swapR["from"][0]) and \
           (swapL["transactionIndex"] <= swapR["transactionIndex"]) and \
           (swapR["transactionIndex"] <= (swapL["transactionIndex"] + MAX_CROSS_TRANSACTION)) and \
           ((swapL["sender"] == swapR["sender"]) if swapL["transactionIndex"] != swapR["transactionIndex"] else True)

def generateLegalCycles(swapsList, currList):
    # print(len(currList))
    if (len(currList) == 0):
        # If current list empty, try start from each swap
        for i, swap in enumerate(swapsList):
            yield from generateLegalCycles([x for j,x in enumerate(swapsList) if j!=i], [swap])
    else:
        # If already a cycle - return it
        if (isCycleClosed(currList)):
            yield currList[:]
        # Try to extend it with swaps from the list
        for i, swap in enumerate(swapsList):
            if (canExtend(currList[-1], swap)):
                yield from generateLegalCycles([x for j,x in enumerate(swapsList) if j!=i], currList + [swap])


def consolidateBalances(b0, b1):
    for key, val in b1.items():
        b0[key] = b0.get(key, 0) + val
    return b0


def isProfitableArbitrageCycle(cycle):
    balances = [{ swap["from"][1] : -1 * swap["from"][0], swap["to"][1] : swap["to"][0] } for swap in cycle]
    combinedBalances = functools.reduce(consolidateBalances, balances)
    if (all(val >= 0 for key, val in combinedBalances.items())):
        return combinedBalances
    return None



TRANSACTION_MULTIPLIER = 1000
LOG_MULTIPLIER = 1
def realTimeOrderQuantity(swap):
    return swap["transactionIndex"] * TRANSACTION_MULTIPLIER + swap["logIndex"] * LOG_MULTIPLIER

def swapId(swap):
    return f'{swap["transactionIndex"]}-{swap["logIndex"]}'

def solve(X, Y, solution=[]):
    if not X:
        yield list(solution)
    else:
        c = min(X, key=lambda c: len(X[c]))
        for r in list(X[c]):
            solution.append(r)
            cols = select(X, Y, r)
            yield from solve(X, Y, solution)
            deselect(X, Y, r, cols)
            solution.pop()

def select(X, Y, r):
    cols = []
    for j in Y[r]:
        for i in X[j]:
            for k in Y[i]:
                if k != j:
                    X[k].remove(i)
        cols.append(X.pop(j))
    return cols

def deselect(X, Y, r, cols):
    for j in reversed(Y[r]):
        X[j] = cols.pop()
        for i in X[j]:
            for k in Y[i]:
                if k != j:
                    X[k].add(i)

""" Prefer in same transaction cycle """
def closenessMeasure(cycle):
    x = [realTimeOrderQuantity(swap) for swap in cycle ]
    return -1 * sum( (x[i] - x[i-1])**2.0 for i in range(1, len(x)) )**0.5


"""
 arbitrages is list of pairs of cycle, balance.
 We want to try and reduce duplicates as much as possible.
 We first favor order: longer is better.
 Then we try to get real-time order.
"""
def reduceArbitrages(arbitrages):

    allSwaps = set() 
    Y = dict()
    X = dict()
    for i, (arbitrage, _) in enumerate(arbitrages):
        currSwaps = {swapId(swap) for swap in arbitrage}
        Y[i] = sorted(list(currSwaps))
        for swap in currSwaps:
            if (swap not in X):
                X[swap] = set()
            X[swap].add(i)
        allSwaps = allSwaps.union(currSwaps)

    ## pprint.pprint(allSwaps)
    ## pprint.pprint(X)
    ## pprint.pprint(Y)

    covers = [cover for cover in solve(X, Y)]
    if (not len(covers)):
        print(f"Couldn't find a cover!!")
        pprint.pprint(allSwaps)
        pprint.pprint(X)
        pprint.pprint(Y)
        pprint.pprint(arbitrages)
        exit(-1)
    else:
        maximal = max(covers, key=lambda cover : (len(cover), 
            sum(closenessMeasure(arbitrage) for i, (arbitrage,_) in enumerate(arbitrages) if i in cover)))
        retArbitrages = [arbitrage for i, arbitrage in enumerate(arbitrages) if i in maximal]
        sumSwaps = sum(len(s[0]) for s in retArbitrages)
        swapIds = len({swapId(x) for s in retArbitrages for x in s[0]})
        pure = swapIds == sumSwaps
        return [(x[0], x[1], list({s["transactionIndex"] for s in x[0]})) for x in retArbitrages], pure



def findInBlockArbitrages(blockNum, blockSwapsList):
    blockSwapsList.sort(key=lambda x : (x["transactionIndex"], x["logIndex"]))
    """
     We want to try and find all pssible arbitrage chains.
     Brite Force Methods:
        We want to enumerate each legal cycle of swaps.
        Legal cycle:
          Needs to satisfy:
            - The to-token of each swap is the from-token of the next.
            - The to-token of the last swap equals the from-token of the first.
            - The to-amount of each swap is greater or equal to the from-amount of the next.
            - The swaps are somehow related through sender/recipient/contract.
            - The swaps don't go back in time between transactions - but can inside a transaction.
        For each cycle:
          We will check if it produced an arbitrage. Meaning the net balance of doing the swaps actually
          produced non-negative values on all tokens. If yes, we return it as a possible arbitrage.
    """
    ret = []
    print(f"Started in block {blockNum} with {len(blockSwapsList)} swaps")
    arbitrages = []
    for cycle in generateLegalCycles(blockSwapsList, []):
        print(f"Found cycle with {len(cycle)} swaps")
        b = isProfitableArbitrageCycle(cycle)
        if (b):
            print(f"Found elementary arbitrage cycle with {len(cycle)} swaps!")
            arbitrages.append((cycle, b))
    if (len(arbitrages)):
        ## Reduce duplicates
        print(f"Block {blockNum} has {len(arbitrages)} elementary arbitrages")
        reducedArbitrages, pure = reduceArbitrages(arbitrages)
        print(f"Block {blockNum} has {len(reducedArbitrages)} reduced arbitrages")
        if (not pure):
            print(f"Reduction isn't pure")
        for cycle, balance, transactions in reducedArbitrages:
            print(f"Found arbitrage in block {blockNum} with: #swaps({len(cycle)}), #transactions({len(transactions)}), multiTransaction({len(transactions) > 1})")
            pprint.pprint(transactions)
            pprint.pprint(balance)
            pprint.pprint(cycle)
            ret.append({"transactions" : transactions, "balance" : balance, "cycle" : cycle})
    return ret


def extractArbitrages(swaps):
    print(f"Started Processing")
    arbitrages = []
    numBlocks = len(swaps)
    numTransactions = 0
    numSwaps = 0
    print(f"Has {numBlocks} blocks")
    for blockNum, transactions in swaps.items():
        currNumTransactions = len(transactions)
        numTransactions += currNumTransactions
        blockSwaps = []
        print(f"Block {blockNum} has {currNumTransactions} transactions")
        for txNum, swapsList in transactions.items():
            blockSwaps += swapsList
            currNumSwaps = len(swapsList)
            numSwaps += currNumSwaps
            print(f"Transaction {txNum} of block {blockNum} has {currNumSwaps} swaps")
        print(f"Block {blockNum} has {len(blockSwaps)} swaps")
        arbitrages.extend(findInBlockArbitrages(blockNum, blockSwaps))
    print(f"There are {numSwaps} swaps in total")
    return arbitrages


def dumpArbitrages(arb):
    try:
        with open(f'data/arbitrages.json', 'w') as json_file:
            json.dump(arb, json_file, indent=4)
    except:
        print(f"Couldn't dump arbitrages!!")
        exit(-1)


def main():
    print(f"Loading Swaps")
    swaps = loadSwapHistory()
    arbitrages = extractArbitrages(swaps)
    print(f"There are {len(arbitrages)} arbitrages in total")
    dumpArbitrages(arbitrages)


if __name__=='__main__':
    main()


