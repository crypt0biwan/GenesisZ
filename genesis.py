#!/usr/bin/python3

import argparse
import asyncio
import sys, os, time

from bitcoin.core import *
from bitcoin.core.script import CScript, OP_CHECKSIG
from zcash.core import *
from pyblake2 import blake2s

args = {}
verbose = False

def main():
    global args
    args = parseArgs()

    eh = buildEquihashInputHeader(args)
    # as if I cared about windows users...
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    solution, nonce = loop.run_until_complete(findValidSolution(eh, args.solver))
    print('Solution found!\nNonce: %s\n%s' % (b2lx(nonce), b2x(solution)))
    loop.close()

def warn(msg):
    sys.stderr.write(msg + '\n')

def fatal(msg):
    sys.stderr.write(msg + '\n')
    sys.exit(1)

def verb(msg):
    if verbose:
        print(msg)

def parseArgs():
    def lbytes32(s):
        """Converts a hex string into a 32 bytes long byte array, litte endian"""
        if len(s) > 32:
            warn('Nonce can be at most 32 bytes long, is %i! Will be truncated' % len(s))
            return lx(s[:64])
        return lx('0'*(64-len(s)) + s)
    def split(s):
        """Runs s.split()"""
        return s.split()

    parser = argparse.ArgumentParser(description="This script uses any Equihash solver to find a solution for the specified genesis block")
    parser.add_argument("-t", "--time",
            dest="time", action="store", type=int, default=int(time.time()),
            help="unix time to set in block header (defaults to current time)")
    parser.add_argument("-z", "--timestamp", dest="timestamp",
            default="The Economist 2016-10-29 Known unknown: Another crypto-currency is born. BTC#436254 0000000000000000044f321997f336d2908cf8c8d6893e88dbf067e2d949487d ETH#2521903 483039a6b6bd8bd05f0584f9a078d075e454925eb71c1f13eaff59b405a721bb DJIA close on 27 Oct 2016: 18,169.68",
            help="the pszTimestamp found in the input transaction script. Will be blake2s'd and then prefixed by coin name")
    parser.add_argument("-C", "--coinname", dest="coinname", default="Zcash",
            help="the coin name prepends the blake2s hash of timestamp in pszTimestamp")
    parser.add_argument("-n", "--nonce", dest="nonce", default=b'\x00'*32,
            type=lbytes32, help="nonce to start with when searching for a valid"
            " equihash solution; parsed as hex")
    parser.add_argument("-p", "--pubkey", dest="pubkey", type=x,
            default=x("04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f"),
            help="the pubkey found in the output script")
    parser.add_argument("-b", "--bits", dest="bits", type=int,
            default=0x1f07ffff,
            help="the target in compact representation, defining a difficulty of 1")
    parser.add_argument("-V", "--value", dest="value", default=0, type=int,
            help="output transaction value in zatoshi (1 ZEC = 100000000 zatoshi)")
    parser.add_argument("-s", "--solver", dest="solver",
            type=split, default=split("sa-solver -n 99999 -i"),
            help="Equihash solver command; must accept the block header in hex as argument.")
    parser.add_argument("-v", "--verbose",
            dest="verbose", action="store_true",
            help="verbose mode")

    args = parser.parse_args()
    global verbose
    verbose = args.verbose

    verb('Start Nonce: ' + b2lx(args.nonce))
    verb('Pubkey: ' + b2x(args.pubkey))
    verb('Solver: %s' % args.solver)

    return args

def buildEquihashInputHeader(args):
    pszTimestamp = args.coinname + \
            blake2s(args.timestamp.encode('UTF-8')).hexdigest()
    verb("pszTimestamp: " + pszTimestamp)
    pk, bits = args.pubkey, args.bits
    # Input transaction
    scriptSig = CScript() + bits + b'\x04' + pszTimestamp.encode('UTF-8')
    txin=CMutableTxIn(scriptSig=scriptSig)
    # Output transaction
    scriptPubKey = CScript() + pk + OP_CHECKSIG
    txout = CMutableTxOut(nValue = args.value, scriptPubKey = scriptPubKey)

    tx = CMutableTransaction(vin=[txin], vout=[txout])
    txhash = tx.GetHash()
    verb("TX/merkle root hash: " + b2lx(txhash))

    return CEquihashHeader(nTime=args.time, nBits=bits,
        nNonce=args.nonce, hashMerkleRoot=txhash)

def stri(b):
    return b.decode('ascii').rstrip()

def findValidSolution(eh, solverCmd):
    """find a valid equihash solution matching the target specified by nBits"""
    verb('Starting solver...')
    create = asyncio.create_subprocess_exec(
            *solverCmd, b2x(eh.serialize()), # TODO or b2lx?
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
    try:
        solver = yield from create
        verb('Solver started.')
    except FileNotFoundError as e:
        warn("Could not find '%s' binary; is the path correct?" \
                % solverCmd[0])
        # exit without using sys.exit() because this raises SystemExit and
        # asyncio catches it and prints a stack trace which confuses end-users.
        os._exit(1)
    except Exception as e:
        fatal("Failed to execute '%s': %s" % (self.solver_binary, e))
    banner = yield from solver.stdout.readline()
    verb('Solver banner: ' + stri(banner))
    while(True):
        nonce, sols = parseSolutions(solver)
        verb('Solver returned %i solutions for nonce %s' % \
                (len(sols), b2lx(nonce)))

    # TODO DUMMY
    return 'solution'.encode('ascii'), b'\xde\xad'



if __name__ == "__main__":
    main()