import json
import time
import datetime
from typing import Optional
from timestamps_tip_scanner.constants import Networks
from timestamps_tip_scanner.event_scanner_state import EventScannerState

from web3.datastructures import AttributeDict


class JSONifiedState(EventScannerState):
    """Store the state of scanned blocks and all events.

    All state is an in-memory dict.
    Simple load/store massive JSON on start up.
    """

    def __init__(self):
        self.state = None
        self.eligible = None
        self.single_tips = None
        self.freports = "report_timestamps.json"
        self.fsingletips = "single_tips.json"
        self.ffeedtips = "feed_tips.json"
        # How many second ago we saved the JSON file
        self.last_save = 0
        self.date = datetime.datetime.today().strftime("%b-%d-%Y")

    def reset(self, network, zero_block=None):
        """Create initial state of nothing scanned."""
        if zero_block is None:
            import requests
            res = requests.get(Networks[network].api_scan)
            result = res.json()
            zero_block = int(result["result"])
            print(f"Starting block was not selected so starting from: {zero_block}")
        else:
            print(f"Scan starting from block: {zero_block}")
        self.state = {
            "last_scanned_block": int(zero_block),
        }

    def restore(self):
        """Restore the last scan state from a file."""
        try:
            self.state = json.load(open(self.freports, "rt"))
            print(
                f"Restored the state, last block scan ended at {self.state['last_scanned_block']}"
            )
        except (IOError, json.decoder.JSONDecodeError):
            print("State starting from scratch")
            self.reset()

    def save(self):
        """Save everything we have scanned so far in a file."""
        with open(self.freports, "wt") as f:
            json.dump(self.state, f)
        self.last_save = time.time()

    def reset_feedtips(self):
        self.feed_tips = {"feed_tips": {}}

    def reset_singletips(self):
        self.single_tips = {"single_tips": {}}

    def timestampsperEOA(self, EOA: str) -> Optional[list[int]]:
        try:
            return self.state[f"{EOA}"]
        except KeyError:
            print(f"Timestamps for {EOA} not found in json!")
            return

    def save_single_tips(self):
        with open(self.fsingletips, "wt") as f:
            json.dump(self.single_tips, f)

    def save_feed_tips(self):
        with open(self.ffeedtips, "wt") as f:
            json.dump(self.feed_tips, f)

    def process_feed_timestamps(self, query_id: str, feed_id: str, timestamp: int):
        feed_tips = self.feed_tips["feed_tips"]
        if query_id not in feed_tips:
            feed_tips[query_id] = {}

        if feed_id not in feed_tips[query_id]:
            feed_tips[query_id][feed_id] = []
            feed_tips[query_id][feed_id].append(timestamp)
        else:
            feed_tips[query_id][feed_id].append(timestamp)
            feed_tips[query_id][feed_id] = [*set(feed_tips[query_id][feed_id])]
    
    def process_feed_timestamps_zero_balance(self, query_id: str, feed_id: str, timestamp: int):
        feed_tips = self.feed_tips["feed_tips"]
        if "feed_tips_no_balance" not in feed_tips:
            feed_tips["feed_tips_no_balance"] = {}
            feed_tips = feed_tips["feed_tips_no_balance"]
        if query_id not in feed_tips:
            feed_tips[query_id] = {}

        if feed_id not in feed_tips[query_id]:
            feed_tips[query_id][feed_id] = []
            feed_tips[query_id][feed_id].append(timestamp)
        else:
            feed_tips[query_id][feed_id].append(timestamp)
            feed_tips[query_id][feed_id] = [*set(feed_tips[query_id][feed_id])]

    def process_singletip_timestamps(self, query_id: str, timestamp: int):
        single_tips = self.single_tips["single_tips"]
        if query_id not in single_tips:
            single_tips[query_id] = []
            single_tips[query_id].append(timestamp)
        else:
            single_tips[query_id].append(timestamp)
            single_tips[query_id] = [*set(single_tips[query_id])]

    #
    # EventScannerState methods implemented below
    #

    def get_last_scanned_block(self):
        """The number of the last block we have stored."""
        return self.state["last_scanned_block"]

    def delete_data(self, since_block):
        """Remove potentially reorganised blocks from the scan data."""
        pass

    def start_chunk(self, block_number, chunk_size):
        pass

    def end_chunk(self, block_number):
        """Save at the end of each block, so we can resume in the case of a crash or CTRL+C"""
        # Next time the scanner is started we will resume from this block
        self.state["last_scanned_block"] = block_number

        # Save the database file for every minute
        if time.time() - self.last_save > 60:
            self.save()

    def process_event(self, event: AttributeDict) -> str:
        """Record NewReport event and tip eligible timestamps."""

        log_index = event.logIndex  # Log index within the block
        txhash = event.transactionHash.hex()  # Transaction hash
        args = event["args"]
        reporter_addr = args._reporter
        query_id = "0x" + args._queryId.hex()

        if reporter_addr not in self.state:
            self.state[reporter_addr] = {}

        reporter = self.state[reporter_addr]

        if query_id not in reporter:
            reporter[query_id] = []

        queryId = reporter[query_id]

        queryId.append(args._time)
        queryId = [*set(queryId)]
        return f"{txhash}-{log_index}"
