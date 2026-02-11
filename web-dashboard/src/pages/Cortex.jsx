import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { BrainCircuit, Cpu, Clock, Target } from 'lucide-react';

const Cortex = () => {
    const [logs, setLogs] = useState([]);
    const [bif, setBif] = useState(null);

    // Fetch Logs
    useEffect(() => {
        let isMounted = true;
        const fetchLogs = async () => {
            if (!isMounted) return;
            try {
                const res = await axios.get(`${API_BASE_URL}/logs?limit=50`);
                if (isMounted) setLogs(res.data);
            } catch (err) {
                console.error(err);
            }
            if (isMounted) setTimeout(fetchLogs, 3000);
        };
        fetchLogs();
        return () => { isMounted = false; };
    }, []);

    // Fetch Real-time State (For BIF)
    useEffect(() => {
        let isMounted = true;
        const fetchState = async () => {
            if (!isMounted) return;
            try {
                const res = await axios.get(`${API_BASE_URL}/state`);
                if (isMounted) setBif(res.data.bif_analysis || {});
            } catch (err) { console.error(err); }
            if (isMounted) setTimeout(fetchState, 1000); // Fast poll for physics
        };
        fetchState();
        return () => { isMounted = false; };
    }, []);

    return (
        <div className="p-4 pt-16 lg:p-8 lg:pt-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-purple-500/10 rounded-xl">
                        <BrainCircuit className="w-8 h-8 text-purple-400" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-white">Neural Cortex</h1>
                        <p className="text-slate-400">Real-time reasoning stream & market physics.</p>
                    </div>
                </div>
            </div>

            {/* BIF PHYSICS ENGINE VISUALIZATION */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 mb-10">
                {/* 1. REGIME STATE */}
                <div className="glass-card p-6 border-t-4 border-t-purple-500 relative overflow-hidden">
                    <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-2">Market Regime</h3>
                    <div className="text-2xl font-bold text-white mb-1">
                        {!bif ? "INITIALIZING..." :
                            bif.hurst > 0.55 ? "TRENDING" :
                                bif.hurst < 0.45 ? "MEAN REVERSION" : "RANDOM WALK"}
                    </div>
                    <div className="text-xs text-purple-300">
                        {bif?.entropy > 0.9 ? "HIGH CHAOS (PAUSED)" : "Valid Structure"}
                    </div>
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                        <Cpu size={64} />
                    </div>
                </div>

                {/* 2. HURST EXPONENT (Memory) */}
                <div className="glass-card p-6">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest">Hurst Memory</h3>
                        <span className="text-white font-mono">{bif?.hurst?.toFixed(3) || "---"}</span>
                    </div>
                    <div className="relative h-4 bg-slate-800 rounded-full overflow-hidden mb-2">
                        {/* Center marker */}
                        <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-white/20 z-10"></div>
                        <div
                            className={`absolute top-0 bottom-0 transition-all duration-1000 ${(bif?.hurst || 0.5) > 0.5 ? "bg-blue-500 left-1/2" : "bg-orange-500 right-1/2"
                                }`}
                            style={{
                                width: `${Math.abs((bif?.hurst || 0.5) - 0.5) * 200}%`,
                                left: (bif?.hurst || 0.5) > 0.5 ? '50%' : 'auto',
                                right: (bif?.hurst || 0.5) < 0.5 ? '50%' : 'auto'
                            }}
                        />
                    </div>
                    <div className="flex justify-between text-[10px] text-slate-500">
                        <span>Reverting (0.0)</span>
                        <span>Random (0.5)</span>
                        <span>Trending (1.0)</span>
                    </div>
                </div>

                {/* 3. ENTROPY (Chaos) */}
                <div className="glass-card p-6">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest">Shannon Entropy</h3>
                        <span className="text-white font-mono">{bif?.entropy?.toFixed(3) || "---"}</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-4 overflow-hidden mb-2">
                        <div
                            className={`h-full transition-all duration-1000 ${(bif?.entropy || 0) > 0.8 ? "bg-red-500" : "bg-green-500"
                                }`}
                            style={{ width: `${(bif?.entropy || 0) * 100}%` }}
                        />
                    </div>
                    <div className="flex justify-between text-[10px] text-slate-500">
                        <span>Ordered (0.0)</span>
                        <span>Chaos (1.0)</span>
                    </div>
                </div>
            </div>

            <div className="space-y-6 relative">

                {/* Connection Line */}
                <div className="absolute left-6 top-4 bottom-4 w-0.5 bg-gradient-to-b from-purple-500/50 to-transparent"></div>

                {logs.map((log, index) => (
                    <div key={index} className="relative pl-16 group">
                        {/* Node Dot */}
                        <div className="absolute left-[21px] top-6 w-3 h-3 rounded-full bg-purple-500 ring-4 ring-fintech-bg group-hover:ring-purple-500/20 transition-all"></div>

                        <div className="glass-card p-6 hover:bg-fintech-card transition-colors">
                            <div className="flex flex-col sm:flex-row justify-between items-start mb-4 gap-2">
                                <div className="flex items-center gap-3">
                                    <span className={`px-2 py-1 rounded text-xs font-bold ${log.Action === 'BUY' ? 'bg-green-500/20 text-green-400' :
                                        log.Action === 'SELL' ? 'bg-red-500/20 text-red-400' :
                                            'bg-slate-700 text-slate-300'
                                        }`}>
                                        {log.Action}
                                    </span>
                                    <span className="text-slate-500 text-xs flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {log.Timestamp}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-slate-500 uppercase">Confidence</span>
                                    <div className="h-1.5 w-16 bg-slate-800 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-purple-500"
                                            style={{ width: `${parseFloat(log.Confidence) * 100}%` }}
                                        />
                                    </div>
                                </div>
                            </div>

                            <p className="text-slate-300 leading-relaxed text-sm font-light">
                                {log.Reasoning}
                            </p>
                        </div>
                    </div>
                ))}

                {logs.length === 0 && (
                    <div className="text-center py-20 text-slate-500 italic">
                        Waiting for initial neural activity...
                    </div>
                )}
            </div>
        </div>
    );
};

export default Cortex;
