import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { Trophy, TrendingUp, TrendingDown, Activity, Zap, Hexagon, Users, Brain } from 'lucide-react';

function DarwinSwarm() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;
        const fetchData = async () => {
            try {
                const response = await axios.get(`${API_BASE_URL}/state`);
                if (isMounted) {
                    setData(response.data);
                    setLoading(false);
                }
            } catch (err) {
                console.error("API Error", err);
            }
            if (isMounted) setTimeout(fetchData, 2000);
        };
        fetchData();
        return () => { isMounted = false; };
    }, []);

    if (loading && !data) return <div className="p-8 text-slate-500 flex items-center gap-3"><Activity className="animate-spin" /> Connecting to Hive Mind...</div>;

    // Handle new Aggregated Structure
    const swarmDetails = data?.darwin_swarm || {};
    const families = swarmDetails.families || {};
    const topPerformers = swarmDetails.top_performers || [];
    const populationSize = swarmDetails.population_size || 0;

    // Fallback for old API structure (while migrating)
    const isLegacy = Array.isArray(data?.darwin_swarm);

    if (isLegacy) {
        return <div className="p-8 text-yellow-500">System Updating... (Legacy API Detected)</div>;
    }

    const leader = topPerformers.length > 0 ? topPerformers[0] : null;

    return (
        <div className="p-8 space-y-8 max-w-[1600px] mx-auto">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        <Hexagon className="text-yellow-500" /> Project Hive (Gen 2)
                    </h1>
                    <div className="text-slate-400 text-sm mt-1 flex gap-4">
                        <span className="flex items-center gap-1"><Users size={14} /> Population: {populationSize}</span>
                        <span className="flex items-center gap-1"><Brain size={14} /> Evolutionary Mode: ACTIVE</span>
                    </div>
                </div>

                {leader && (
                    <div className="flex gap-6">
                        <div className="glass-card px-6 py-3 border border-yellow-500/30 bg-yellow-500/5">
                            <div className="text-xs text-yellow-500 uppercase font-bold mb-1">Alpha Leader</div>
                            <div className="text-xl font-mono font-bold text-white">{leader.name}</div>
                            <div className="text-sm text-slate-400">Score: {leader.score?.toFixed(0)}</div>
                        </div>
                    </div>
                )}
            </div>

            {/* ORACLE BRIEFING */}
            {data?.oracle_brief && (
                <div className="glass-card p-6 border-l-4 border-l-blue-500 bg-blue-500/5 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                        <Zap size={100} />
                    </div>
                    <div className="flex items-start gap-4 relaltive z-10">
                        <div className="p-3 bg-blue-500/20 rounded-full text-blue-400">
                            <Activity size={24} />
                        </div>
                        <div>
                            <h3 className="text-sm font-bold text-blue-400 uppercase tracking-wider mb-1">The Oracle (Market Narrative)</h3>
                            <p className="text-xl text-slate-200 font-light leading-relaxed">"{data.oracle_brief}"</p>
                        </div>
                    </div>
                </div>
            )}

            {/* FAMILY AGGREGATION GRID */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
                {Object.entries(families).map(([familyName, stats]) => (
                    <div key={familyName} className="glass-card p-5 border border-slate-700/50 hover:border-blue-500/30 transition-all">
                        <h3 className="text-lg font-bold text-slate-200 mb-2">{familyName}</h3>

                        <div className="grid grid-cols-2 gap-4 mb-4">
                            <div>
                                <div className="text-[10px] text-slate-500 uppercase">Agents</div>
                                <div className="text-xl font-mono text-slate-300">{stats.count}</div>
                            </div>
                            <div>
                                <div className="text-[10px] text-slate-500 uppercase">Avg IQ</div>
                                <div className={`text-xl font-mono ${stats.avg_score > 80 ? 'text-green-400' : 'text-slate-400'}`}>
                                    {stats.avg_score.toFixed(0)}
                                </div>
                            </div>
                        </div>

                        <div className="bg-slate-800/50 rounded p-2 text-xs">
                            <div className="text-slate-500 mb-1">Best Variant</div>
                            <div className="text-yellow-400 font-mono truncate" title={stats.best_agent}>
                                {stats.best_agent}
                            </div>
                            <div className="text-right text-slate-500 mt-1">Score: {stats.best_score.toFixed(0)}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* ELITE LEADERBOARD */}
            <div className="glass-card p-6">
                <h3 className="text-lg font-bold text-slate-300 mb-4 flex items-center gap-2">
                    <Trophy size={18} className="text-yellow-500" />
                    Elite Performers (Top 10)
                </h3>
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="text-xs text-slate-500 border-b border-slate-700">
                                <th className="p-3 pl-0">Rank</th>
                                <th className="p-3">Strategy Name</th>
                                <th className="p-3 text-right">Score</th>
                                <th className="p-3 text-right">Total Equity</th>
                                <th className="p-3 text-right">Win/Loss</th>
                                <th className="p-3 text-right">Drawdown</th>
                            </tr>
                        </thead>
                        <tbody>
                            {topPerformers.map((s, i) => (
                                <tr key={s.name} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                                    <td className="p-3 pl-0 font-mono text-slate-500">#{i + 1}</td>
                                    <td className="p-3 font-medium text-slate-200 font-mono text-sm">{s.name}</td>
                                    <td className="p-3 text-right font-bold text-yellow-500">{s.score.toFixed(0)}</td>
                                    <td className={`p-3 text-right font-mono ${s.equity >= 10000 ? 'text-green-400' : 'text-red-400'}`}>
                                        ${(s.equity - 10000).toFixed(2)}
                                    </td>
                                    <td className="p-3 text-right text-slate-400 text-sm">
                                        <span className="text-green-400">{s.wins}</span> / <span className="text-red-400">{s.losses}</span>
                                    </td>
                                    <td className="p-3 text-right text-red-400 text-sm">{(s.dd * 100).toFixed(2)}%</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

export default DarwinSwarm;
