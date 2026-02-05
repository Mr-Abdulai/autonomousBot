import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { Wallet, ArrowUpRight, ArrowDownRight, History } from 'lucide-react';

const Ledger = () => {
    const [logs, setLogs] = useState([]);

    useEffect(() => {
        const fetchLogs = async () => {
            try {
                const res = await axios.get(`${API_BASE_URL}/logs?limit=100`);
                // Filter only executed trades (BUY/SELL)
                const executedTrades = res.data.filter(log => ['BUY', 'SELL'].includes(log.Action));
                setLogs(executedTrades);
            } catch (err) {
                console.error(err);
            }
        };
        fetchLogs();
    }, []);

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-blue-500/10 rounded-xl">
                    <Wallet className="w-8 h-8 text-blue-400" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold text-white">Ledger</h1>
                    <p className="text-slate-400">Historical trade records and risk events.</p>
                </div>
            </div>

            <div className="glass-card overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-fintech-border bg-slate-900/50 text-slate-400 text-xs uppercase tracking-wider">
                            <th className="p-4 font-medium">Time</th>
                            <th className="p-4 font-medium">Symbol</th>
                            <th className="p-4 font-medium">Action</th>
                            <th className="p-4 font-medium text-right">Entry</th>
                            <th className="p-4 font-medium text-right">SL</th>
                            <th className="p-4 font-medium text-right">TP</th>
                            <th className="p-4 font-medium text-right">Size</th>
                            <th className="p-4 font-medium text-right">PnL</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-fintech-border/50 text-sm">
                        {logs.map((row, i) => (
                            <tr key={i} className="hover:bg-white/5 transition-colors">
                                <td className="p-4 text-slate-500 font-mono">{row.Timestamp.split(' ')[1]}</td>
                                <td className="p-4 text-white font-bold">{row.Symbol}</td>
                                <td className="p-4">
                                    <span className={`flex items-center gap-1 font-bold ${row.Action === 'BUY' ? 'text-green-400' :
                                        row.Action === 'SELL' ? 'text-red-400' : 'text-slate-400'
                                        }`}>
                                        {row.Action === 'BUY' && <ArrowUpRight className="w-4 h-4" />}
                                        {row.Action === 'SELL' && <ArrowDownRight className="w-4 h-4" />}
                                        {row.Action}
                                    </span>
                                </td>
                                <td className="p-4 text-right font-mono text-slate-300">{row.Entry || '-'}</td>
                                <td className="p-4 text-right font-mono text-slate-500">{row.SL || '-'}</td>
                                <td className="p-4 text-right font-mono text-slate-500">{row.TP || '-'}</td>
                                <td className="p-4 text-right font-mono text-blue-300">{row.Size || '-'}</td>
                                <td className={`p-4 text-right font-mono font-bold ${(row.PnL || 0) > 0 ? 'text-green-400' : (row.PnL || 0) < 0 ? 'text-red-400' : 'text-slate-600'
                                    }`}>
                                    {row.PnL ? `$${row.PnL}` : '--'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {logs.length === 0 && (
                    <div className="p-8 text-center text-slate-500">No records found.</div>
                )}
            </div>
        </div>
    );
};

export default Ledger;
