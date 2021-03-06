
import json
import pprint
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from collections import Counter

"""
Information about the collected Data:
  - SWAPS_START_BLOCK = 14020000 : Jan-17-2022 01:07:37 AM +UTC
  - SWAPS_END_BLOCK   = 14050000 : Jan-21-2022 04:30:45 PM +UTC
  - Collected from UniSwapV3, UniSwapV2 and SushiSwap
  - Prices are current day prices according to coinbase
  - Ethereum's price is take from WETH token
"""

SWAPS_START_BLOCK = 14020000
SWAPS_END_BLOCK   = 14050000

WETH_ADDRESS = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"

def loadJson(file):
    with open(file, 'r', encoding='utf-8') as json_file:
        return json.load(json_file)
    try:
        with open(file, 'r') as json_file:
            return json.load(json_file)
    except:
        print(f"Couldn't load {file}!!")
        exit(-1)

def loadSwapHistory():
    return loadJson(f'data/swap_history.json')

def loadArbitrages():
    return loadJson(f'data/arbitrages.json')

def loadTokenInfo():
    return loadJson(f'data/token_info.json')

def loadPools(tokens):
    dex_mapping = {"uniswapv2" : "UniSwapV2", "uniswapv3" : "UniSwapV3", "sushiswap" : "SushiSwap"}
    pools = dict()
    dexes = ["uniswapv2", "uniswapv3", "sushiswap"]
    for dex in dexes:
        for pool in loadJson(f'data/{dex}_pools.json'):
            try:
                symbol = {'token0' : getSymbol(pool['token0'], tokens), 'token1' : getSymbol(pool['token1'], tokens)}
                if symbol["token0"] == "WETH":
                    token_left, token_right = "token0", "token1"
                elif symbol["token1"] == "WETH":
                    token_left, token_right = "token1", "token0"
                elif symbol["token0"] > symbol["token1"]:
                    token_left, token_right = "token0", "token1"
                else:
                    token_left, token_right = "token1", "token0"
                name = f"{dex_mapping[dex]} - {symbol[token_left]}/{symbol[token_right]}"
                pools[pool["poolContract"]] = {
                    "contractAddress" : pool["poolContract"],
                    "dex" : dex,
                    "name" : name
                }
            except:
                pass
    return pools


"""
 Global Statistics
"""
class BasicStatistics:
    def __init__(self):
        self.start_block, self.end_block = 0, 0      # Blocks start and end
        self.num_total_blocks = 0                    # Blocks num
        self.num_total_swaps = 0                     # Swaps num
        self.num_total_transactions = 0              # Transactions num
        self.num_total_pools = 0                     # Pools num
        self.swaps_in_pool = dict()                  # Map pools to number of swaps
        self.transactions_in_block = dict()          # Map blockNum   to number of transactions in it
        self.swaps_in_transactions = dict()          # Map (blockNum, txNum) to num of swaps in it
        self.swaps_in_blocks = dict()                # Map blockNum to num of swaps in it
        self.swaps_in_dexes = dict()                 # Map dex to num of swaps in it


def getBasicStatistics(swaps, arbitrages, tokens):
    stats = BasicStatistics()
    stats.start_block = SWAPS_START_BLOCK
    stats.end_block = SWAPS_END_BLOCK
    stats.num_total_blocks = stats.end_block - stats.start_block
    for blockNum, transactions in swaps.items():
        stats.num_total_transactions += len(transactions)
        for txNum, swapsList in transactions.items():
            stats.num_total_swaps += len(swapsList)
            stats.swaps_in_transactions[(int(blockNum), int(txNum))] = len(swapsList)
            stats.swaps_in_blocks[int(blockNum)] = stats.swaps_in_blocks.get(int(blockNum), 0) + len(swapsList)
            for swap in swapsList:
                stats.swaps_in_dexes[swap["dex"]] = stats.swaps_in_dexes.get(swap["dex"], 0) + 1
                stats.swaps_in_pool[swap["poolAddress"]] = stats.swaps_in_pool.get(swap["poolAddress"], 0) + 1
        stats.transactions_in_block[int(blockNum)] = len(transactions)
    stats.num_total_pools = len(stats.swaps_in_pool.keys())
    return stats


"""
 Statistics per Arbitrage
"""
class ArbitrageStatistics:
    def __init__(self):
        self.transactionHashes = []
        self.block_num = 0                           # The blockNumber of arbitrage
        self.num_transactions = 0                    # Number of transactions in cycle
        self.multi_transaction = False               # Is sandwitch ?
        self.sandwitch_start_index = -1              # For a sandwitch: start index
        self.num_swaps = 0                           # Number of swaps in cycle
        self.num_tokens = 0                          # Number of used tokens
        self.swaps_in_pool = dict()                  # Map pools to number of swaps
        self.initiator = None                        # The initiator of the arbitrage chain
        self.exchanges = dict()                      # Map each exchange to number of swaps on it
        self.balances = dict()                       # The balance of tokens for the arbitrage in its token
        self.balances_usd = dict()                   # The balance of tokens for the arbitrage in USD
        self.fees_wei = 0                            # Total fees in WEI paid for arbitrage
        self.fees_usd = 0                            # Total fees in USD paid for arbitrage
        self.profit_usd = 0                          # Total profit in USD for arbitrage
        self.net_profit_usd = 0                      # Profit - Fees in USD



def getPrice(amount, token_address, tokens):
    token_info = tokens[token_address]
    assert(token_info["USD"] != None and token_info["decimals"] != None), (token_address, token_info)
    return (float(amount) * token_info["USD"]) / (10**token_info["decimals"])

def getSymbol(token_address, tokens):
    token_info = tokens[token_address]
    assert(token_info["symbol"] != None), (token_address, token_info)
    return token_info["symbol"]


def getArbitrageStatistics(arbitrage, tokens):
    stats = ArbitrageStatistics()
    stats.block_num = arbitrage["cycle"][0]["blockNumber"]
    stats.num_transactions = len(arbitrage["transactions"])
    stats.multi_transaction = stats.num_transactions > 1
    if (stats.multi_transaction):
        stats.sandwitch_start_index = min(arbitrage["transactions"])
    stats.num_swaps = len(arbitrage["cycle"])
    stats.num_tokens = len(arbitrage["balance"])
    fees = dict()
    for swap in arbitrage["cycle"]:
        stats.swaps_in_pool[swap["poolAddress"]] = stats.swaps_in_pool.get(swap["poolAddress"], 0) + 1
        stats.exchanges[swap["dex"]] = stats.exchanges.get(swap["dex"], 0) + 1
        fees[swap["transactionIndex"]] = int(swap["gasUsed"], 16) * int(swap["gasPrice"], 16)
        if swap["transactionHash"] not in stats.transactionHashes: 
            stats.transactionHashes.append(swap["transactionHash"])
    stats.initiator = arbitrage["cycle"][0]["sender"]
    stats.fees_wei = sum(fees.values())
    stats.fees_usd = getPrice(stats.fees_wei, WETH_ADDRESS, tokens)
    for token_address, amount in arbitrage["balance"].items():
        stats.balances[getSymbol(token_address, tokens)] = amount
        stats.balances_usd[getSymbol(token_address, tokens)] = getPrice(amount, token_address, tokens) if amount else 0
    stats.profit_usd = sum(stats.balances_usd.values())
    stats.net_profit_usd = stats.profit_usd - stats.fees_usd
    return stats


def analyze(swaps, arbitrages, tokens):
    basic_stats = getBasicStatistics(swaps, arbitrages, tokens)
    arbitrage_stats = [getArbitrageStatistics(arbitrage, tokens) for arbitrage in arbitrages]
    return basic_stats, arbitrage_stats

def playWithStatistics(basic_stats, arbitrage_stats):
    # Get heighest/lowest amounts
    print("Highest")
    pprint.pprint([x.__dict__ for x in sorted(arbitrage_stats, key=lambda x:x.net_profit_usd, reverse=True)[:10]])
    print("Lowest")
    pprint.pprint([x.__dict__ for x in sorted(arbitrage_stats, key=lambda x:x.net_profit_usd, reverse=True)[-10:]])
    # Get profits
    profits = dict()
    for arbitrage in arbitrage_stats:
        for token, amount in arbitrage.balances_usd.items():
            profits[token] = profits.get(token, 0) + amount
    print("Profits")
    pprint.pprint(sorted(profits.items(), key=lambda x:x[1]))
    # Print
    pprint.pprint(vars(basic_stats))
    for arbitrage in arbitrage_stats:
        pprint.pprint(vars(arbitrage))


def printStats(swaps, arbitrages, tokens, basic_stats, arbitrage_stats):
    print(f"Start block 14020000 : Jan-17-2022 01:07:37 AM +UTC")
    print(f"End block 14050000 : Jan-21-2022 04:30:45 PM +UTC")
    print(f"Total number of blocks: {basic_stats.num_total_blocks}")
    print(f"Total number of transactions: {basic_stats.num_total_transactions}")
    print(f"Number of blocks with swaps is {len(basic_stats.swaps_in_blocks)}")
    print(f"Total number of pools used: {basic_stats.num_total_pools}")
    print(f"Total number of swaps: {basic_stats.num_total_swaps}")
    
def bucketing(xs, ys, bucket_size):
    new_x_min = min(xs) - (min(xs) % bucket_size)
    new_xs = list(range(new_x_min, max(xs)+1, bucket_size))
    new_ys = [0] * len(new_xs)
    for x, y in zip(xs, ys):
        new_x = x - (x % bucket_size)
        new_x_idx = int((new_x - new_x_min)/bucket_size)
        new_ys[new_x_idx] += y
    return new_xs, new_ys

def createSwapsInArbitrageGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats):
    ## Create data
    block_sequence = range(basic_stats.start_block, basic_stats.end_block + 1)
    all_swaps = [ basic_stats.swaps_in_blocks.get(b, 0) for b in block_sequence ]
    arbitrage_swaps_d = dict()
    for arb in arbitrage_stats:
        arbitrage_swaps_d[arb.block_num] = arbitrage_swaps_d.get(arb.block_num, 0) + arb.num_swaps
    arbitrage_swaps = [ arbitrage_swaps_d.get(b, 0) for b in block_sequence ]
    ## Print Statistics
    number_of_swaps_in_arbitrages = sum(arbitrage_swaps)
    percentage = float(number_of_swaps_in_arbitrages)/sum(all_swaps)
    print(f"Number of blocks with arbitrages is {len(arbitrage_swaps_d)}")
    print(f"Number of swaps in arbitrages is {number_of_swaps_in_arbitrages} : {percentage}")
    ## Graph: On x-axis block number. On y-axis: total swaps and swaps in arbitrage
    fig, axs = plt.subplots(1, 2, figsize=([11.6, 4.8]), gridspec_kw={'width_ratios': [3, 1]})
    fig.suptitle("Swaps Count per Block: Total vs. Swaps in Arbitrages")
    bucket_size = 100
    block_sequence_buckets, all_swaps_buckets = bucketing(block_sequence, all_swaps, bucket_size)
    block_sequence_buckets, arbitrage_swaps_buckets = bucketing(block_sequence, arbitrage_swaps, bucket_size)
    axs[0].plot(block_sequence_buckets, all_swaps_buckets , label='Total')
    axs[0].plot(block_sequence_buckets, arbitrage_swaps_buckets, label='Swaps in Arbitrages')
    axs[0].set_xlabel('Block Number')
    axs[0].set_ylabel(f'Number of Swaps per {bucket_size} Blocks')
    axs[0].set_title(f"Swaps Count per {bucket_size} Blocks")
    axs[0].ticklabel_format(useOffset=False, style='plain')
    axs[0].set_xticks(range(basic_stats.start_block, basic_stats.end_block+1, 10000))
    axs[0].legend()
    axs[1].bar(['Total', 'Swaps in Arbitrages'], [np.average(all_swaps), np.average(arbitrage_swaps)])
    for bar in axs[1].patches:
        axs[1].annotate(format(bar.get_height(), '.2f'), (bar.get_x() + bar.get_width() / 2, bar.get_height()), ha='center', va='center',
                   size=10, xytext=(0, 4), textcoords='offset points')
    axs[1].set_ylabel('Number of Swaps')
    axs[1].set_title("Avarage Number of Swaps per Block")
    plt.tight_layout()
    plt.savefig('outputs/swaps_in_arbitrage.png')
    plt.close(fig)


def portion_graph(total_value, portions_labels, portions_values, title, ylabel, output_path, fig_type="pie"):
    portions_labels = [str(x) for x in portions_labels]
    fig, ax = plt.subplots()
    if fig_type == "bar":
        ax.set_title(title)
        ax.bar(['Total'] + portions_labels, [total_value] + portions_values)
        ax.set_ylabel(ylabel)
    else:
        assert(fig_type == "pie")
        ax.set_title(title + f"\n(Total {ylabel}: {int(total_value)})")
        ax.pie(portions_values, labels=portions_labels, autopct='%1.1f%%')
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close(fig)


def createArbitragesGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats):
    ## Create data
    block_sequence = range(basic_stats.start_block, basic_stats.end_block + 1)
    arbitrage_blocks_d = dict()
    for arb in arbitrage_stats:
        arbitrage_blocks_d[arb.block_num] = arbitrage_blocks_d.get(arb.block_num, 0) + 1
    arbitrage_blocks = [ arbitrage_blocks_d.get(b, 0) for b in block_sequence ]
    ## Number of arbitrages in total
    arbitrage_total_count = len(arbitrage_stats)
    sandwiches_count = len([x for x in arbitrage_stats if x.multi_transaction])
    in_transaction_arbitrage_count = len([x for x in arbitrage_stats if not x.multi_transaction])
    print(f"There are {arbitrage_total_count} arbitrages in total")
    print(f"There are {sandwiches_count} sandwiches")
    print(f"There are {in_transaction_arbitrage_count} in-transaction arbitrages")

    ## Graph: Arbitrage Types: In-transaction vs. Sandwich
    portion_graph(arbitrage_total_count, ['Multi-Transaction', 'Single-Transaction'],
                  [sandwiches_count, in_transaction_arbitrage_count],
                  "Arbitrage Types Count: Single-Transaction vs. Multi-Transaction", 'Arbitrage Count', 'outputs/arbitrages_types.png',
                  "pie")


    ## Graph: Number of arbitrages in each block : x - block number, y - arbitrages number
    bucket_size = 100
    block_sequence_buckets, arbitrage_blocks_buckets = bucketing(block_sequence, arbitrage_blocks, bucket_size)
    fig, ax = plt.subplots()
    ax.plot(block_sequence_buckets, arbitrage_blocks_buckets)
    ax.set_xlabel('Block Number')
    ax.set_ylabel('Number of Arbitrages')
    ax.set_title(f"Arbitrage Count Per {bucket_size} Blocks")
    ax.ticklabel_format(useOffset=False, style='plain')
    ax.set_xticks(range(basic_stats.start_block, basic_stats.end_block+1, 10000))
    plt.savefig('outputs/arbitrages_in_blocks.png')
    plt.close(fig)

    ## Table of number of arbitrages in each block
    c = Counter(arbitrage_blocks)
    print(f"Average number of arbitrages per-block is {np.average(arbitrage_blocks)}")
    print(f"Counters for number of arbitrages in block")
    x = []
    y = []
    for num, total in sorted(c.items()):
        x.append(num)
        y.append(total)
        print(f"Arbitrages {num} in {total} blocks")
    print(f"Number of blocks with arbitrage: {len(arbitrage_blocks_d.keys())}")
    fig, ax = plt.subplots()
    ax.bar(x, y)
    for bar in ax.patches:
        ax.annotate(bar.get_height(), (bar.get_x() + bar.get_width() / 2, bar.get_height()), ha='center', va='center',
                   size=10, xytext=(0, 4), textcoords='offset points')
    ax.set_xlabel('Number of Arbitrages in Block')
    ax.set_ylabel('Number of Blocks')
    ax.set_title("Number of Arbitrages in a Single Block Histogram")
    ax.ticklabel_format(useOffset=False, style='plain')
    plt.savefig('outputs/num_arbitrages_in_block.png')
    plt.close(fig)


    ## Histogram of frequency between arbitrages in blocks
    frequencies = []
    prev = 0
    for current_block in sorted(arbitrage_blocks_d.keys()):
        if prev == 0:
            prev = current_block
        else:
            frequencies.append(current_block - prev - 1)
            prev = current_block
    c = Counter(frequencies)
    x = []
    y = []
    for a, b in sorted(c.items()):
        x.append(a)
        y.append(b)
    fig, ax = plt.subplots()
    ax.bar(x, y)
    ax.set_xlabel('Number of Blocks Between Arbitrages')
    ax.set_ylabel('Frequency')
    ax.set_title("Arbitrages Frequency")
    ax.ticklabel_format(useOffset=False, style='plain')
    plt.savefig('outputs/arbitrages_frequency.png')
    plt.close(fig)
   
def createExchangesGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats):
    mapping = { "uniswapv3" : "UniV3", "uniswapv2" : "UniV2", "sushiswap" : "Sushi"}
    ## Create data
    print(f"Total number of swaps: {basic_stats.num_total_swaps}")
    for dex, num_of_swaps in basic_stats.swaps_in_dexes.items():
        print(f"Num swaps in {dex} is {num_of_swaps}: {num_of_swaps/float(basic_stats.num_total_swaps)}")
    exchanges = []
    for arb in arbitrage_stats:
        exchanges.append("-".join(sorted([mapping[x] for x in arb.exchanges])))
    c = Counter(exchanges)
    keys = []
    values = []
    for k,v in c.items():
        keys.append(k)
        values.append(v)
    ## Exchange combinations Pie Chart
    fig, ax = plt.subplots()
    ax.pie(values, labels=keys, autopct='%1.1f%%')
    ax.set_title('Exchanges Used in Arbitrages')
    ax.axis('equal')
    plt.savefig('outputs/dex_pie.png')
    plt.close(fig)


def createPoolsGraph(swaps, arbitrages, tokens, pools, basic_stats, arbitrage_stats):
    ## Collect Data
    pools_hist = dict()
    for arb in arbitrage_stats:
        for p,v in arb.swaps_in_pool.items():
            pools_hist[pools[p]["name"]] = pools_hist.get(pools[p]["name"], 0) + v
    ## Print Stats
    print(f"Used {len(pools_hist.keys())} pools in arbitrages")
    all_pools = sorted(pools_hist.items(), key=lambda x: x[1], reverse=True)
    print(f"Average number of swaps per pool is {sum([x[1] for x in all_pools])/float(len(all_pools))}")
    ## Top 20 pools participating in arbitrage
    top_pools = all_pools[:20]
    print(f"Top 20 pools used in arbitrage")
    for p,v in top_pools:
        print(f"Pool {p} : {v}")

    ## graph: top pools bars
    fig, ax = plt.subplots(figsize=([8, 6]))
    ax.bar([p[0] for p in top_pools], [p[1] for p in top_pools])
    ax.set_title("Top Pools: 20 Most Used for Arbitrage")
    ax.set_ylabel("Swaps Count")
    ax.set_xlabel("Pool Name")
    for label in ax.get_xticklabels():
        label.set_rotation(80)
    ax.grid()
    plt.tight_layout()
    plt.savefig('outputs/top_pools_bars.png')
    plt.close(fig)



def createFeesAndProfitsGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats):
    mapping = { "uniswapv3" : "UniV3", "uniswapv2" : "UniV2", "sushiswap" : "Sushi"}
    ## Collect Data
    profits_by_exchange = dict()
    profits_by_type = dict()
    total_fees_wei = []
    total_fees_usd = []
    total_profit_usd = []
    total_net_profit_usd = []
    info = []
    for arb in sorted(arbitrage_stats, key=lambda x:x.profit_usd):
        total_fees_wei.append(arb.fees_wei)
        total_fees_usd.append(arb.fees_usd)
        total_profit_usd.append(arb.profit_usd)
        total_net_profit_usd.append(arb.net_profit_usd)
        info.append(arb)
        profits_by_type[arb.multi_transaction] = profits_by_type.get(arb.multi_transaction, 0) + arb.net_profit_usd
        dexes = "-".join(sorted([mapping[x] for x in arb.exchanges]))
        profits_by_exchange[dexes] = profits_by_exchange.get(dexes, 0) + arb.net_profit_usd
    print(f"Total fees paid in ETH: {float(sum(total_fees_wei))/10**18}")
    print(f"Total fees paid in USD : {sum(total_fees_usd)}")
    print(f"Total profit in USD : {sum(total_profit_usd)}")
    print(f"Total net profits in USD : {sum(total_net_profit_usd)}")
    print(f"There are {len(arbitrage_stats)} arbitrages in total")
    print(f"Profitable: {sum(1 for x in total_net_profit_usd if x > 0)}")
    print(f"Not-Profitable: {sum(1 for x in total_net_profit_usd if x <= 0)}")

    ## graph:  profit (and loss) histogram
    fig, ax = plt.subplots()
    total_profit_usd_np = np.array(total_profit_usd)
    outliers_bitmap = (total_profit_usd_np > 3000)
    outliers_percentage = (sum(outliers_bitmap) / len(total_profit_usd)) * 100
    total_profit_usd_filtered = total_profit_usd_np[np.bitwise_not(outliers_bitmap)]
    ax.hist(total_profit_usd_filtered, 20)
    ax.set_title("Histogram of Arbitrage Profit \n(Dropped Outliers: {:.2f}%)".format(outliers_percentage))
    ax.set_xlabel("Profit [USD]")
    ax.set_ylabel("Arbitrage Count")
    plt.savefig('outputs/profit_hist.png')
    plt.close(fig)

    ## graph: net profit (and loss) histogram
    fig, ax = plt.subplots()
    total_net_profit_usd_np = np.array(total_net_profit_usd)
    outliers_bitmap = np.bitwise_or((total_net_profit_usd_np > 600), (total_net_profit_usd_np < -200))
    outliers_percentage = (sum(outliers_bitmap) / len(total_net_profit_usd_np)) * 100
    total_net_profit_usd_filtered = total_net_profit_usd_np[np.bitwise_not(outliers_bitmap)]
    ax.hist(total_net_profit_usd_filtered, 20)
    ax.set_title("Histogram of Arbitrage Net-Profit \n(Dropped Outliers: {:.2f}%)".format(outliers_percentage))
    ax.set_xlabel("Profit [USD]")
    ax.set_ylabel("Arbitrage Count")
    plt.savefig('outputs/net_profit_hist.png')
    plt.close(fig)

    ## graph: fee histogram
    fig, ax = plt.subplots()
    total_fees_usd_np = np.array(total_fees_usd)
    outliers_bitmap = total_fees_usd_np>1500
    outliers_percentage = (sum(outliers_bitmap) / len(total_fees_usd_np)) * 100
    total_fees_usd_filtered = total_fees_usd_np[np.bitwise_not(outliers_bitmap)]
    ax.hist(total_fees_usd_filtered, 20)
    ax.set_title("Histogram of Fees \n(Dropped Outliers: {:.2f}%)".format(outliers_percentage))
    ax.set_xlabel("Fee [USD]")
    ax.set_ylabel("Arbitrage Count")
    plt.savefig('outputs/fee_hist.png')
    plt.close(fig)

    ## graph: profit fee correlation
    fig, axs = plt.subplots(1, 2, figsize=([12.8, 4.8]))
    total_profit_usd_np = np.array(total_profit_usd)
    total_fees_usd_np = np.array(total_fees_usd)
    outliers_bitmap = total_profit_usd_np>10000
    outliers_percentage = (sum(outliers_bitmap) / len(total_profit_usd_np)) * 100
    total_fees_usd_filtered = total_fees_usd_np[np.bitwise_not(outliers_bitmap)]
    total_profit_usd_filtered = total_profit_usd_np[np.bitwise_not(outliers_bitmap)]
    axs[0].scatter(total_fees_usd_filtered, total_profit_usd_filtered)
    axs[0].set_title("Profit vs. Fee for Majority of Arbitrages")
    axs[0].set_xlabel("Fee [USD]")
    axs[0].set_ylabel("Profit [USD]")
    total_fees_usd_outliers = total_fees_usd_np[outliers_bitmap]
    total_profit_usd_outliers = total_profit_usd_np[outliers_bitmap]
    axs[1].scatter(total_fees_usd_outliers, total_profit_usd_outliers)
    axs[1].set_title("Profit vs. Fee for Outliers")
    axs[1].set_xlabel("Fee [USD]")
    axs[1].set_ylabel("Profit [USD]")
    plt.savefig('outputs/profit_fee_correlation_separated.png')
    plt.close(fig)

    ## graph: profit fee correlation
    fig, ax = plt.subplots()
    ax.scatter(total_fees_usd, total_profit_usd)
    ax.set_title("profit  vs. fee")
    ax.set_xlabel("fee [USD]")
    ax.set_ylabel("profit [USD]")
    plt.savefig('outputs/profit_fee_correlation.png')
    plt.close(fig)




    ## Top 20 - Fees
    top_fees = sorted(arbitrage_stats, key=lambda x:x.fees_usd, reverse=True)[:20]
    print(f"Average fee: {float(sum(total_fees_usd))/len(arbitrage_stats)}")
    print("Top 20 Fees paid in usd:")
    for arb in top_fees:
        print(f"{arb.fees_usd} usd : {arb.transactionHashes}")
    ## Top 50 - Profits
    print(f"Average Net-Profit: {float(sum(total_net_profit_usd))/len(arbitrage_stats)}")
    top_profit = sorted(arbitrage_stats, key=lambda x:x.net_profit_usd, reverse=True)[:50]
    print("Top 50 profit in usd:")
    for arb in top_profit:
        print(f"{arb.net_profit_usd} usd : {arb.transactionHashes}")
    ## Lowest 20 - Profits
    lowest_profit = sorted(arbitrage_stats, key=lambda x:x.net_profit_usd)[:20]
    print("Lowest 20 profit in usd:")
    for arb in lowest_profit:
        print(f"{arb.net_profit_usd} usd : {arb.transactionHashes}")
    ## Profits by type
    print(f"Total net profits in USD : {sum(total_net_profit_usd)}")
    print(f"Division by type (true: sandwitch):")
    pprint.pprint(profits_by_type)

    ## graph: profits by type pie
    portion_graph(sum(total_net_profit_usd), ['Multi-Transaction', 'Single-Transaction'],
                  [profits_by_type[True], profits_by_type[False]],
                  "Net USD Profit\nArbitrage Types: Single-Transaction vs. Multi-Transaction", 'Net Profit [USD]',
                  'outputs/profit_arbitrages_types.png',
                  "pie")

    ## Profits by dex
    print(f"Division by dex:")
    pprint.pprint(profits_by_exchange)

    keys = []
    values = []
    for k,v in sorted(profits_by_exchange.items(), key=lambda x:x[1], reverse=True):
        keys.append(k)
        values.append(int(v))

    ## graph: Exchanges Combination Pie
    fig, ax = plt.subplots()
    wedges, texts, autotexts = ax.pie(values, labels=keys, autopct=lambda pct: "{:.1f}%".format(pct))
    ax.set_title('Profits for Exchanges Combination')
    ax.axis('equal')
    plt.savefig('outputs/dex_profits_pie.png')
    plt.close(fig)

    ## Main/Collateral Profits
    arbitrage_cnt = len(arbitrage_stats)
    exact_cnt = 0
    main_profits = 0
    collateral_profits = 0
    for arb in arbitrage_stats:
        if sum(1 for k,v in arb.balances.items() if v!= 0) == 1:
            exact_cnt += 1
        # Main is the maximal one
        main_profits += max(arb.balances_usd.values())
        # Collateral is the rest
        collateral_profits += arb.profit_usd - max(arb.balances_usd.values())
    print(f"Out of {arbitrage_cnt} arbitrage, {exact_cnt} are exact!")
    print(f"Main profits = {main_profits}, collateral_profits = {collateral_profits}")
    
    ## ## Graph Fees paid for arbitrages along with profits and net-profits
    ## fig, ax = plt.subplots()
    ## ax.plot(range(len(arbitrage_stats)), total_fees_usd, label="Fees")
    ## #ax.plot(range(len(arbitrage_stats)), total_profit_usd, label="Profit")
    ## #ax.plot(range(len(arbitrage_stats)), total_net_profit_usd, label="Net-Profit")
    ## ax.set_xlabel('Arbitrage Index')
    ## ax.set_ylabel('Amount [USD]')
    ## ax.set_title("Fees and Profits for Arbitrages")
    ## ax.legend()
    ## plt.savefig('outputs/fees_and_profits.png')
    ## plt.show()
    ## plt.close(fig)

   
def createTokensGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats):
    ## Collect Data
    token_arbitrages_num = dict()   ## Map token to number of arbitrages that used it
    token_profit_amount = dict()    ## Map token to profit amount
    token_profited_num = dict()     ## Times token was used for profit
    token_internal_num = dict()     ## Times token was used internally
    num_tokens_used = dict()        ## Number of tokens used
    num_tokens_profited = dict()    ## Number of tokens used
    for arb in arbitrage_stats:
        for token, balance in arb.balances.items():
            token_arbitrages_num[token] = token_arbitrages_num.get(token, 0) + 1
            token_profited_num[token] = token_profited_num.get(token, 0) + (1 if balance > 0 else 0)
            token_internal_num[token] = token_internal_num.get(token, 0) + (1 if balance == 0 else 0)
        for token, balance in arb.balances_usd.items():
            token_profit_amount[token] = token_profit_amount.get(token, 0) + balance
        num_tokens_used[arb.num_tokens] = num_tokens_used.get(arb.num_tokens, 0) + 1
        x = len([v for v in arb.balances.values() if v != 0])
        num_tokens_profited[x] = num_tokens_profited.get(x, 0) + 1
        ## if (x == 4):
        ##     print("XXX")
        ##     pprint.pprint(arb.__dict__)
        ## if (arb.num_tokens >= 6):
        ##     print("Large number of tokens arbitrages:")
        ##     print(arb.transactionHashes)
    ## Print statistics
    print(f"Top used tokens:")
    pprint.pprint(sorted([x for x in token_arbitrages_num.items()], key = lambda x:x[1], reverse=True)[:20])
    print(f"Top profits tokens:")
    pprint.pprint(sorted([x for x in token_profit_amount.items()], key = lambda x:x[1], reverse=True)[:20])
    print(f"Top src/dst tokens:")
    pprint.pprint(sorted([x for x in token_profited_num.items()], key = lambda x:x[1], reverse=True)[:20])
    print(f"Top internal tokens:")
    pprint.pprint(sorted([x for x in token_internal_num.items()], key = lambda x:x[1], reverse=True)[:20])
    print(f"Number of different tokens used")
    pprint.pprint(num_tokens_used)
    print(f"Number of different tokens profited from")
    pprint.pprint(num_tokens_profited)

    ## graph: top tokens used
    top_tokens_arbitrage_count = sorted(list(token_arbitrages_num.items()), key=lambda x: x[1], reverse=True)[:20]
    fig, ax = plt.subplots()
    ax.bar([t[0] for t in top_tokens_arbitrage_count], [t[1] for t in top_tokens_arbitrage_count])
    ax.set_title("Top 20 Tokens Used in Arbitrage")
    ax.set_ylabel("Number Arbitrages that Used Token")
    ax.set_xlabel("Token Symbol")
    for label in ax.get_xticklabels():
        label.set_rotation(70)
    ax.grid()
    plt.tight_layout()
    plt.savefig('outputs/top_tokens_arbitrage_count.png')
    plt.close(fig)

    ## graph: top tokens profit number
    top_tokens_profit = sorted(list(token_profited_num.items()), key=lambda x: x[1], reverse=True)[:20]
    fig, ax = plt.subplots()
    ax.bar([t[0] for t in top_tokens_profit], [t[1] for t in top_tokens_profit])
    ax.set_title("Top 20 Tokens Profited From in Arbitrages - Count")
    ax.set_ylabel("Number Arbitrages that Profited from Token")
    ax.set_xlabel("Token Symbol")
    for label in ax.get_xticklabels():
        label.set_rotation(70)
    ax.grid()
    plt.tight_layout()
    plt.savefig('outputs/top_tokens_profit_num.png')
    plt.close(fig)

    ## graph: top tokens profit
    top_tokens_profit = sorted(list(token_profit_amount.items()), key=lambda x: x[1], reverse=True)[:20]
    fig, ax = plt.subplots()
    ax.bar([t[0] for t in top_tokens_profit], [t[1] for t in top_tokens_profit])
    ax.set_title("Top 20 Tokens Profited From in Arbitrages - Profit")
    ax.set_ylabel("Total Profit from Token [USD]")
    ax.set_xlabel("Token Symbol")
    for label in ax.get_xticklabels():
        label.set_rotation(70)
    ax.grid()
    plt.tight_layout()
    plt.savefig('outputs/top_tokens_profit.png')
    plt.close(fig)

    ## graph: different tokens used
    x = []
    y = []
    for k, v in num_tokens_used.items():
        x.append(k)
        y.append(v)
    fig, ax = plt.subplots()
    ax.bar(x, y)
    for bar in ax.patches:
        ax.annotate(bar.get_height(), (bar.get_x() + bar.get_width() / 2, bar.get_height()), ha='center', va='center',
                   size=10, xytext=(0, 4), textcoords='offset points')
    ax.set_xlabel('Number of Different Tokens Used in Same Arbitrage')
    ax.set_ylabel('Number of Arbitrages')
    ax.set_title("Number of Tokens Used in Arbitrage")
    ax.ticklabel_format(useOffset=False, style='plain')
    plt.savefig('outputs/num_tokens_in_arbitrage.png')
    plt.close(fig)



def createCycleGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats):
    ## Collect Data
    total_cycle_len = dict()
    in_transaction_cycle_len = dict()
    sandwitch_cycle_len = dict()
    sandwitch_transaction_num = dict()
    sandwitch_start_transaction_index = dict()
    for arb in arbitrage_stats:
        total_cycle_len[arb.num_swaps] = total_cycle_len.get(arb.num_swaps, 0) + 1
        if (arb.multi_transaction):
            sandwitch_cycle_len[arb.num_swaps] = sandwitch_cycle_len.get(arb.num_swaps, 0) + 1
            sandwitch_transaction_num[arb.num_transactions] = sandwitch_transaction_num.get(arb.num_transactions, 0) + 1
            sandwitch_start_transaction_index[arb.sandwitch_start_index] = sandwitch_start_transaction_index.get(arb.sandwitch_start_index, 0) + 1
            ## if (arb.num_transactions >= 3):
            ##     print(f"Arbitrage on more than 2 transactions:")
            ##     pprint.pprint(arb.__dict__)
        else:
            in_transaction_cycle_len[arb.num_swaps] = in_transaction_cycle_len.get(arb.num_swaps, 0) + 1
            ## if (arb.num_swaps >= 6):
            ##     print(f"Arbitrage on more than 6 swap:")
            ##     pprint.pprint(arb.__dict__)
    ## Print Stats
    print("Total Cycle length:")
    pprint.pprint(sorted([x for x in total_cycle_len.items()], key = lambda x:x[1], reverse=True))
    print("In-Transaction Cycle length:")
    pprint.pprint(sorted([x for x in in_transaction_cycle_len.items()], key = lambda x:x[1], reverse=True))
    print("Sandwitch Cycle length:")
    pprint.pprint(sorted([x for x in sandwitch_cycle_len.items()], key = lambda x:x[1], reverse=True))
    print("Sandwitch Transaction length:")
    pprint.pprint(sorted([x for x in sandwitch_transaction_num.items()], key = lambda x:x[1], reverse=True))
    print("Sandwitch Start index:")
    pprint.pprint(sorted([x for x in sandwitch_start_transaction_index.items()], key = lambda x:x[0]))
        
    ## graph: cycles length
    in_trans_cycle_len_pairs = sorted([x for x in total_cycle_len.items()], key=lambda x: x[1], reverse=True)
    in_trans_lengths =  [x[0] for x in in_trans_cycle_len_pairs]
    in_trans_counts = [x[1] for x in in_trans_cycle_len_pairs]
    portion_graph(sum(total_cycle_len.values()), in_trans_lengths, in_trans_counts,
                  "Cycle Length for Arbitrages - Number of Swaps", "Cycle Count", "outputs/cycle_len.png", "bar")
    x = []
    y = []
    for k, v in total_cycle_len.items():
        x.append(k)
        y.append(v)
    fig, ax = plt.subplots()
    ax.bar(x, y)
    for bar in ax.patches:
        ax.annotate(bar.get_height(), (bar.get_x() + bar.get_width() / 2, bar.get_height()), ha='center', va='center',
                   size=10, xytext=(0, 4), textcoords='offset points')
    ax.set_xlabel('Number of Swaps in Arbitrage')
    ax.set_ylabel('Number of Arbitrages')
    ax.set_title("Cycle Length - Number of Swaps in Arbitrage")
    ax.ticklabel_format(useOffset=False, style='plain')
    plt.savefig('outputs/cycle_length.png')
    plt.close(fig)


 

def extractSpecificArbitrages(swaps, arbitrages, tokens, basic_stats, arbitrage_stats):
    pass
    ## ## Single vs Multi
    ## done = [0, 0]
    ## for arb in arbitrage_stats:
    ##     if arb.multi_transaction and len(arb.balances) == 2 and len(arb.exchanges) == 1 and sum(x > 0 for x in arb.balances.values()) == 1:
    ##         done[0] += 1
    ##         print("Multi-Transaction")
    ##         pprint.pprint(arb.__dict__)
    ##     if not arb.multi_transaction and len(arb.balances) == 3 and len(arb.exchanges) == 1 and sum(x > 0 for x in arb.balances.values()) == 1:
    ##         done[1] += 1
    ##         print("Single-Transaction")
    ##         pprint.pprint(arb.__dict__)
    ##     if (all(x >= 3 for x in done)):
    ##         break
    ## ## Cross exchange
    ## done = [0]
    ## for arb in arbitrage_stats:
    ##     if len(arb.exchanges) >= 3 and sum(x > 0 for x in arb.balances.values()) == 1:
    ##         done[0] += 1
    ##         pprint.pprint(arb.__dict__)
    ##     if (all(x >= 3 for x in done)):
    ##         break
    ## ## Same exchange
    ## done = [0]
    ## for arb in arbitrage_stats:
    ##     if len(arb.exchanges) == 1 and sum(x > 0 for x in arb.balances.values()) == 1:
    ##         done[0] += 1
    ##         pprint.pprint(arb.__dict__)
    ##     if (all(x >= 3 for x in done)):
    ##         break
    ## ## Same exchange two tokesn
    ## done = [0]
    ## for arb in arbitrage_stats:
    ##     if len(arb.exchanges) == 1 and not arb.multi_transaction and len(arb.balances) == 2 and sum(x > 0 for x in arb.balances.values()) == 1:
    ##         done[0] += 1
    ##         pprint.pprint(arb.__dict__)
    ##     if (all(x >= 3 for x in done)):
    ##         break
    ## ## Owned token
    ## done = [0]
    ## for arb in arbitrage_stats:
    ##     if len(arb.exchanges) == 1 and not arb.multi_transaction and len(arb.balances) == 2 and sum(x > 0 for x in arb.balances.values()) == 1:
    ##         done[0] += 1
    ##         pprint.pprint(arb.__dict__)
    ##     if (all(x >= 3 for x in done)):
    ##         break
    ## ## Other token
    ## done = [0]
    ## for arb in arbitrage_stats:
    ##     if  not arb.multi_transaction and sum(x > 0 for x in arb.balances.values()) == 1 and "WETH" in arb.balances and arb.balances["WETH"] == 0:
    ##         done[0] += 1
    ##         pprint.pprint(arb.__dict__)
    ##     if (all(x >= 3 for x in done)):
    ##         break
    ## ## Imprecise
    ## done = [0]
    ## for arb in arbitrage_stats:
    ##     if  not arb.multi_transaction and sum(x > 0 for x in arb.balances.values()) == 2 and 1 in arb.balances.values():
    ##         done[0] += 1
    ##         pprint.pprint(arb.__dict__)
    ##     if (all(x >= 3 for x in done)):
    ##         break


def main():
    print(f"Loading data")
    swaps = loadSwapHistory()
    arbitrages = loadArbitrages()
    tokens = loadTokenInfo()
    pools = loadPools(tokens)
    print(f"Analyzing")
    basic_stats, arbitrage_stats = analyze(swaps, arbitrages, tokens)
    ## playWithStatistics(basic_stats, arbitrage_stats):
    print(f"Extract Specific Arbitrages")
    extractSpecificArbitrages(swaps, arbitrages, tokens, basic_stats, arbitrage_stats)
    print(f"Creating Graphs")
    printStats(swaps, arbitrages, tokens, basic_stats, arbitrage_stats)
    createSwapsInArbitrageGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats)
    createArbitragesGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats)
    createExchangesGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats)
    createPoolsGraph(swaps, arbitrages, tokens, pools, basic_stats, arbitrage_stats)
    createFeesAndProfitsGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats)
    createTokensGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats)
    createCycleGraph(swaps, arbitrages, tokens, basic_stats, arbitrage_stats)

    """
        Things to show in data collection:
          x 1. Start/End Blocks + Number of swaps in total and in each exchange
          x 2. Number of swaps/swaps in arbitrages in each block : x - block number, y - swaps
          x 3. Number of arbitrages in each block : x - block number, y - arbitrages number
          x 3. Table for number of arbitrages per block
          x 4. Frequency of arbitrages: How many blocks pass between the arbitrages : histogram of frequencies
          x 2. Swaps in each dex: Pie chart of swaps per DEX
          x 8. Pie chart for arbitrages and dex combinations
          x     For each combination of exchanges (2^3) - how many arbitrages used them.
          x     How many used UniSwapV3 alone, how many used all of them, ???
          x 6. Histogram of pools used in total : Identify top hitters
          x 7. Histogram of pools utilized for arbitrages
          x 8. Fees graph for arbitrages
          x 9. Profits and net-profit graphs on arbitrages
          x 9. Profits by exchange combination
          x 9. profits by type: in-transaction/sandwitch
          x 10. Exact and non-exact profits
          x 9. For each token type how many swaps on it and how many arbitrages used it - Bars
          x 10. For each token - how many times as src/dst and how many as internal
          x 11. For each token: how much is profited from it.
          x 6. For in-transaction: Cycle length. Histogram of arbitrage cycle lengths.
          x 7. For sandwitches: Cycle length and number of transactions maybe ?
          x 8. For sandwitches: Placement in block
    """

    
if __name__=='__main__':
    import psutil
    for p in psutil.process_iter():
        if p.name() == 'Acrobat.exe':
            p.kill()
    main()

