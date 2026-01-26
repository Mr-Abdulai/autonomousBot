import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { Activity, Zap, TrendingUp, BarChart2 } from 'lucide-react';

const DeepMarket = () => {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;
        const fetchHistory = async () => {
            if (!isMounted) return;
            try {
                const res = await axios.get(`${API_BASE_URL}/history`);
                if (isMounted) setHistory(res.data);
            } catch (err) {
                console.error("Failed to load market history", err);
            } finally {
                if (isMounted) setLoading(false);
            }
            // Poll every 5s safely
            if (isMounted) setTimeout(fetchHistory, 5000);
        };

        fetchHistory();
        return () => { isMounted = false; };
    }, []);

    if (loading) return <div className="p-8 text-slate-500">Loading Market Data...</div>;

    if (history.length === 0) return (
        <div className="p-8 text-center">
            <h2 className="text-2xl font-bold text-slate-600 mb-2">No Historical Data</h2>
            <p className="text-slate-500">The bot needs to run for a few cycles to accumulate chart history.</p>
        </div>
    );

    const lastCandle = history[history.length - 1];
    const prevCandle = history[history.length - 2] || lastCandle;
    const isUp = lastCandle.close > prevCandle.close;

    return (
        <div className="p-8 space-y-6 max-w-7xl mx-auto h-screen flex flex-col">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        <Activity className="text-blue-500" />
                        Deep Market
                    </h1>
                    <div className="text-slate-400 text-sm mt-1">Real-time Technical Analysis Feed</div>
                </div>

                <div className="flex gap-6">
                    <PriceStat label="Current Price" value={lastCandle.close.toFixed(2)} trend={isUp ? 'up' : 'down'} />
                    <PriceStat label="EMA (50)" value={lastCandle.EMA_50?.toFixed(2)} />
                    <PriceStat label="EMA (200)" value={lastCandle.EMA_200?.toFixed(2)} />
                </div>
            </div>

            {/* Main Chart */}
            <div className="glass-card p-4 flex-1 min-h-0 flex flex-col">
                <div className="flex-1 w-full relative">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={history}>
                            <defs>
                                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                            <XAxis
                                dataKey="time"
                                hide={true}
                            />
                            <YAxis
                                domain={['auto', 'auto']}
                                orientation="right"
                                tick={{ fill: '#64748b', fontSize: 12 }}
                                stroke="#1e293b"
                            />
                            <Tooltip content={<CustomTooltip />} />
                            <Area
                                type="monotone"
                                dataKey="close"
                                stroke="#3b82f6"
                                fillOpacity={1}
                                fill="url(#colorPrice)"
                                strokeWidth={2}
                                isAnimationActive={false}
                            />
                            <Area
                                type="monotone"
                                dataKey="EMA_50"
                                stroke="#10b981"
                                fill="none"
                                strokeWidth={1}
                                strokeDasharray="5 5"
                                isAnimationActive={false}
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
};

const PriceStat = ({ label, value, trend }) => (
    <div className="text-right">
        <div className="text-xs text-slate-500 uppercase font-medium mb-1">{label}</div>
        <div className={`text-2xl font-mono font-bold ${trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-white'}`}>
            {value ?? '---'}
        </div>
    </div>
);

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-fintech-card/90 backdrop-blur border border-slate-700 p-3 rounded-lg shadow-xl text-xs">
                <div className="text-slate-400 mb-2">{label}</div>
                {payload.map((p) => (
                    <div key={p.dataKey} className="flex justify-between gap-4 mb-1">
                        <span className="text-slate-300 capitalize">{p.dataKey}:</span>
                        <span className="font-mono text-white font-bold">{p.value.toFixed(2)}</span>
                    </div>
                ))}
            </div>
        );
    }
    return null;
};

export default DeepMarket;
