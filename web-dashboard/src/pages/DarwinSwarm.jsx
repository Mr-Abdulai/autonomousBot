import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { Trophy, TrendingUp, TrendingDown, Activity, Zap } from 'lucide-react';

function DarwinSwarm() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;
        const fetchData = async () => {
            if (!isMounted) return;
            try {
                const response = await axios.get(`${API_BASE_URL}/state`);
                if (isMounted) setData(response.data);
            } catch (err) {
                console.error("API Error", err);
            }
            if (isMounted) setTimeout(fetchData, 2000);
        };
        fetchData();
        return () => { isMounted = false; };
    }, []);

    if (loading && !data) return <div className="p-8 text-slate-500">Connecting to Swarm Intel...</div>;

    const swarm = data?.darwin_swarm || [];
    const leader = swarm.length > 0 ? swarm[0] : null;

    return (
        <div className="p-8 space-y-6 max-w-7xl mx-auto">
            <h1 className="text-3xl font-bold text-white mb-6">Darwinian Evolution</h1>

            {/* LEADER BOARD */}
            {leader && (
                <div className="grid grid-cols-3 gap-6 mb-8">
                    <div className="glass-card p-6 border-l-4 border-l-yellow-500">
                        <div className="flex items-center gap-3 mb-2">
                            <Trophy className="text-yellow-400" />
                            <div className="text-sm text-slate-400 uppercase">Alpha Leader</div>
                        </div>
                        <div className="text-2xl font-bold text-white">{leader.name}</div>
                        <div className="text-sm text-yellow-500 mt-1">{leader.direction} Strategy</div>
                    </div>

                    <div className="glass-card p-6">
                        <div className="flex items-center gap-3 mb-2">
                            <Activity className="text-blue-400" />
                            <div className="text-sm text-slate-400 uppercase">Darwin Score</div>
                        </div>
                        <div className="text-2xl font-bold text-white">{leader.score?.toFixed(0)}</div>
                        <div className="text-xs text-slate-500 mt-1">Selection Metric</div>
                    </div>

                    <div className="glass-card p-6">
                        <div className="flex items-center gap-3 mb-2">
                            <Zap className="text-green-400" />
                            <div className="text-sm text-slate-400 uppercase">Virtual Equity</div>
                        </div>
                        <div className="text-2xl font-bold text-green-400">${leader.equity?.toFixed(2)}</div>
                        <div className="text-xs text-slate-500 mt-1">Simulated Performance</div>
                    </div>
                </div>
            )}

            {/* SWARM TABLE */}
            <div className="glass-card overflow-hidden">
                <div className="p-4 border-b border-slate-700 bg-slate-800/50">
                    <h2 className="text-lg font-bold text-white">Strategy Ecosystem ({swarm.length})</h2>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead className="bg-slate-800/50 text-slate-400 font-mono">
                            <tr>
                                <th className="p-4">Rank</th>
                                <th className="p-4">Strategy Name</th>
                                <th className="p-4">Focus</th>
                                <th className="p-4 text-right">Score</th>
                                <th className="p-4 text-right">Equity</th>
                                <th className="p-4 text-center">W / L</th>
                                <th className="p-4 text-right">DD %</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/50">
                            {swarm.map((strat, idx) => (
                                <tr key={strat.name} className="hover:bg-slate-700/30 transition-colors">
                                    <td className="p-4 font-mono text-slate-500">#{idx + 1}</td>
                                    <td className="p-4 font-bold text-white">
                                        {strat.name}
                                        {idx === 0 && <span className="ml-2 text-xs bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">LEADER</span>}
                                    </td>
                                    <td className="p-4">
                                        <span className={`px-2 py-1 rounded text-xs font-bold ${strat.direction === 'LONG' ? 'bg-green-500/10 text-green-400' :
                                                strat.direction === 'SHORT' ? 'bg-red-500/10 text-red-400' : 'bg-blue-500/10 text-blue-400'
                                            }`}>
                                            {strat.direction}
                                        </span>
                                    </td>
                                    <td className="p-4 text-right font-mono text-blue-300">{strat.score?.toFixed(0)}</td>
                                    <td className="p-4 text-right font-mono text-green-400">${strat.equity?.toFixed(2)}</td>
                                    <td className="p-4 text-center font-mono">
                                        <span className="text-green-500">{strat.wins}</span> / <span className="text-red-500">{strat.losses}</span>
                                    </td>
                                    <td className="p-4 text-right font-mono text-red-400">{strat.drawdown ? (strat.drawdown * 100).toFixed(2) : '0.00'}%</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {!swarm.length && (
                    <div className="p-8 text-center text-slate-500">
                        Waiting for Swarm Intel...
                    </div>
                )}
            </div>
        </div>
    );
}

export default DarwinSwarm;
