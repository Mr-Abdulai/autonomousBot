import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { Trophy, TrendingUp, TrendingDown, Activity, Zap, Hexagon } from 'lucide-react';

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

    const swarm = data?.darwin_swarm || [];
    const leader = swarm.length > 0 ? swarm[0] : null;

    // Group Strategies
    const species = {
        "TrendHawk (Trend Followers)": swarm.filter(s => s.name.includes("TrendHawk")),
        "MeanReverter (Band Faders)": swarm.filter(s => s.name.includes("MeanRev")),
        "RSI Matrix (Scalpers)": swarm.filter(s => s.name.includes("RSI")),
        "MACD Cross (Momentum)": swarm.filter(s => s.name.includes("MACD")),
        "Elite Snipers (Confluence)": swarm.filter(s => s.name.includes("Sniper"))
    };

    const getHeatColor = (equity) => {
        if (equity > 10050) return "bg-emerald-500/20 border-emerald-500/50 text-emerald-400";
        if (equity > 10000) return "bg-green-500/10 border-green-500/30 text-green-400";
        if (equity < 9950) return "bg-red-500/20 border-red-500/50 text-red-400";
        if (equity < 10000) return "bg-rose-500/10 border-rose-500/30 text-rose-400";
        return "bg-slate-700/30 border-slate-600 text-slate-400";
    };

    return (
        <div className="p-8 space-y-8 max-w-[1600px] mx-auto">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        <Hexagon className="text-yellow-500" /> Project Hive
                    </h1>
                    <div className="text-slate-400 text-sm mt-1">Active Swarm Intelligence: {swarm.length} Nodes</div>
                </div>

                {leader && (
                    <div className="flex gap-6">
                        <div className="glass-card px-6 py-3 border border-yellow-500/30 bg-yellow-500/5">
                            <div className="text-xs text-yellow-500 uppercase font-bold mb-1">Current Alpha</div>
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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {Object.entries(species).map(([groupName, strats]) => (
                    <div key={groupName} className="glass-card p-6">
                        <h3 className="text-lg font-bold text-slate-300 mb-4 border-b border-slate-700 pb-2 flex justify-between">
                            {groupName}
                            <span className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-500">{strats.length} Variants</span>
                        </h3>
                        <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-3">
                            {strats.map(s => {
                                const isLeader = leader?.name === s.name;
                                const shortName = s.name.replace(/TrendHawk_|MeanRev_|RSI_Matrix_|MACD_Cross_|Sniper_/, '')
                                    .replace('LONG_', 'L_')
                                    .replace('SHORT_', 'S_')
                                    .replace('BOTH_', 'Bi_');

                                return (
                                    <div
                                        key={s.name}
                                        className={`
                                            metric-card p-2 rounded border transition-all duration-300 relative group
                                            ${getHeatColor(s.equity)}
                                            ${isLeader ? 'ring-2 ring-yellow-400 shadow-[0_0_15px_rgba(250,204,21,0.3)]' : 'hover:scale-105'}
                                        `}
                                    >
                                        {/* Leader Crown */}
                                        {isLeader && <div className="absolute -top-2 -right-2 text-yellow-400"><Trophy size={14} fill="currentColor" /></div>}

                                        <div className="text-[10px] uppercase tracking-wider font-bold truncate opacity-70 mb-1" title={s.name}>
                                            {shortName}
                                        </div>

                                        <div className="text-lg font-bold font-mono text-center">
                                            {s.score?.toFixed(0)}
                                        </div>

                                        <div className={`text-[10px] font-mono text-center ${s.equity >= 10000 ? 'text-green-400' : 'text-red-400'}`}>
                                            ${(s.equity - 10000).toFixed(0)}
                                        </div>

                                        {/* Hover Tooltip */}
                                        <div className="absolute opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 border border-slate-700 p-2 rounded shadow-xl z-10 -bottom-12 left-0 w-32 pointer-events-none">
                                            <div className="text-xs text-slate-300">Win/Loss: <span className="text-green-400">{s.wins}</span>/<span className="text-red-400">{s.losses}</span></div>
                                            <div className="text-xs text-slate-300">DD: {(s.drawdown * 100).toFixed(2)}%</div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default DarwinSwarm;
