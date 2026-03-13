import { TronWeb } from 'tronweb';
import { createPublicClient, http, formatEther, parseAbi } from 'viem';
import { bscTestnet } from 'viem/chains';

async function main() {
    const tronAddress = 'TB1JKi9cPxrwy34n4iVYif8W7h9mfn9vXD';
    const evmAddress = '0x0B5D66620843DBA7eeb6819043c54484e92B5bD4';
    
    console.log("Checking TRON Nile...");
    const tw = new TronWeb({ fullHost: 'https://nile.trongrid.io' });
    const trxBalance = await tw.trx.getBalance(tronAddress);
    console.log(`TRX Balance: ${tw.fromSun(trxBalance)} TRX`);
    
    tw.setAddress(tronAddress);
    try {
        const trc20Contract = await tw.contract().at('TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj');
        const usdtBalance = await trc20Contract.balanceOf(tronAddress).call();
        console.log(`Nile USDT Balance (atomic): ${usdtBalance.toString()}`);
    } catch(e: any) {
        console.log('Error fetching Nile USDT', e.message);
    }
    
    console.log("\nChecking BSC Testnet...");
    const publicClient = createPublicClient({ chain: bscTestnet, transport: http('https://data-seed-prebsc-1-s1.bnbchain.org:8545') });
    const bnbBalance = await publicClient.getBalance({ address: evmAddress });
    console.log(`BNB Balance: ${formatEther(bnbBalance)} BNB`);
    
    try {
        const bep20Balance = await publicClient.readContract({
            address: '0x337610d27c682E347C9cD60BD4b3b107C9d34dDd',
            abi: parseAbi(['function balanceOf(address) view returns (uint256)']),
            functionName: 'balanceOf',
            args: [evmAddress]
        });
        console.log(`BSC USDT Balance (atomic): ${bep20Balance.toString()}`);
    } catch (e: any) {
        console.log('Error fetching BSC USDT', e.message);
    }
}
main();
