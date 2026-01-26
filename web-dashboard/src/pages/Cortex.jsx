import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { BrainCircuit, Cpu, Clock, Target } from 'lucide-react';

const Cortex = () => {
    const [logs, setLogs] = useState([]);

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

    return (
        <div className="p-8 max-w-5xl mx-auto">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-purple-500/10 rounded-xl">
                    <BrainCircuit className="w-8 h-8 text-purple-400" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold text-white">Neural Cortex</h1>
                    <p className="text-slate-400">Real-time reasoning stream from the AI Strategist.</p>
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
                            <div className="flex justify-between items-start mb-4">
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
