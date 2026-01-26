import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { TrendingUp, AlertTriangle, Shield, Activity, Power, Wallet, DollarSign, Percent, Target, Layers } from 'lucide-react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

function Cockpit() {
    const [data, setData] = useState(null);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch System State
    useEffect(() => {
        let isMounted = true;
        const fetchData = async () => {
            if (!isMounted) return;
            try {
                const response = await axios.get(`${API_BASE_URL}/state`);
                if (isMounted) {
                    setData(response.data);
                    setError(null);
                }
            } catch (err) {
                if (isMounted) setError('Connection Lost');
            }
            if (isMounted) setTimeout(fetchData, 2000);
        };
        fetchData();
        return () => { isMounted = false; };
    }, []);

    // Fetch History for Mini Chart
    useEffect(() => {
        let isMounted = true;
        const fetchHistory = async () => {
            if (!isMounted) return;
            try {
                const res = await axios.get(`${API_BASE_URL}/history`);
                if (isMounted && res.data.length > 0) setHistory(res.data);
            } catch (err) {
                console.error("Chart data error", err);
            }
            if (isMounted) setTimeout(fetchHistory, 10000); // Slower poll for chart
        };
        fetchHistory();
        return () => { isMounted = false; };
    }, []);

    if (loading && !data) return <div className="p-8 text-slate-500">Initializing Uplink...</div>;

    const market = data?.market_data || {};
    const activeTrades = data?.active_trades || [];
    const activeTrade = activeTrades?.[0];
    const decision = data?.last_decision || {};

    return (
        <div className="p-8 space-y-6 max-w-7xl mx-auto">
            {/* 1. Header & Identity */}
            <div className="flex items-center justify-between mb-2">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-1 tracking-tight">Command Cockpit</h1>
                    <div className="flex items-center gap-2 text-sm">
                        <span className={`px-2 py-0.5 rounded-full ${error ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'} border border-white/10`}>
                            {error ? '⚠ OFFLINE' : '● OPERATIONAL'}
                        </span>
                        <span className="text-slate-500">|</span>
                        <span className="text-slate-400">Last Sync: {new Date().toLocaleTimeString()}</span>
                    </div>
                </div>
            </div>

            {/* 2. Financial Dashboard (The "Money" Row) */}
            <div className="grid grid-cols-5 gap-4">
                <MetricCardSmall icon={<Target className="text-yellow-400" />} label="Daily PnL" value={data?.daily_pnl} isCurrency highlight={data?.daily_pnl > 0} />
                <MetricCardSmall icon={<Layers className="text-indigo-400" />} label="Total PnL (90d)" value={data?.total_pnl} isCurrency />

                <MetricCardSmall icon={<Wallet className="text-blue-400" />} label="Floating PnL" value={data?.profit} isCurrency />
                <MetricCardSmall icon={<DollarSign className="text-green-400" />} label="Balance" value={data?.balance} isCurrency />
                <MetricCardSmall icon={<Activity className="text-purple-400" />} label="Equity" value={data?.equity} isCurrency highlight />
            </div>

            {/* Main Grid */}
            <div className="grid grid-cols-12 gap-6">

                {/* Left Col: Active Trade */}
                <div className="col-span-4 space-y-6">
                    <div className={`glass-card p-6 relative overflow-hidden ${activeTrade ? 'border-l-4 border-l-blue-500' : 'border-l-4 border-l-slate-700'}`}>
                        <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                            <TrendingUp className="w-5 h-5 text-blue-400" />
                            Active Position
                        </h2>

                        {activeTrades && activeTrades.length > 0 ? (
                            <div className="flex flex-col gap-3 max-h-[200px] overflow-y-auto pr-2 custom-scrollbar relative z-10">
                                {activeTrades.map((trade, idx) => (
                                    <div key={idx} className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50 hover:border-slate-600 transition-colors">
                                        <div className="flex justify-between items-center mb-2">
                                            <div className="flex items-center gap-2">
                                                <span className="font-mono font-bold text-white text-sm">{trade.symbol}</span>
                                                <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${trade.action === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                                                    }`}>
                                                    {trade.action}
                                                </span>
                                            </div>
                                            <span className="text-xs font-mono text-slate-300">
                                                {trade.volume} Lot
                                            </span>
                                        </div>

                                        <div className="grid grid-cols-3 gap-2 text-xs">
                                            <div>
                                                <div className="text-slate-500 mb-0.5">Entry</div>
                                                <div className="text-slate-200">{Number(trade.open_price).toFixed(5)}</div>
                                            </div>
                                            <div>
                                                <div className="text-slate-500 mb-0.5">SL / Pips</div>
                                                <div className="text-red-400 font-mono">
                                                    {trade.sl_pips ? `${trade.sl_pips.toFixed(1)}` : '--'}
                                                </div>
                                            </div>
                                            <div>
                                                <div className="text-slate-500 mb-0.5">TP / Pips</div>
                                                <div className="text-green-400 font-mono">
                                                    {trade.tp_pips ? `${trade.tp_pips.toFixed(1)}` : '--'}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="h-40 flex flex-col items-center justify-center text-slate-500 border border-dashed border-slate-800 rounded-lg">
                                <Shield className="w-8 h-8 mb-2 opacity-30" />
                                <span className="text-sm">No Active Trades</span>
                            </div>
                        )}
                        {/* Background Decor */}
                        <div className="absolute -right-6 -bottom-6 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl pointer-events-none"></div>
                    </div>

                    {/* AI Decision Summary */}
                    <div className="glass-card p-6">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-lg font-bold text-slate-200">Neural Sentiment</h2>
                            <span className="text-xs text-slate-500 animate-pulse">● Live</span>
                        </div>

                        {/* Context: Trend Compass */}
                        <div className="mb-4">
                            <TrendCompass d1={market?.trend_d1} h4={market?.trend_h4} m15={market?.trend_m15} />
                        </div>

                        <div className="text-sm text-slate-400 leading-relaxed min-h-[60px]">
                            {decision.reasoning || "Waiting for next tick analysis..."}
                        </div>
                        {decision.confidence > 0 && (
                            <div className="mt-4">
                                <div className="flex justify-between text-xs mb-1">
                                    <span className="text-slate-400">Confidence</span>
                                    <span className="text-white">{(decision.confidence * 100).toFixed(0)}%</span>
                                </div>
                                <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-blue-500 transition-all duration-500"
                                        style={{ width: `${decision.confidence * 100}%` }}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Col: Ticker & Mini Chart */}
                <div className="col-span-8 flex flex-col gap-6">
                    {/* Ticker Row */}
                    <div className="grid grid-cols-4 gap-4">
                        <MetricCard title="RSI (14)" value={market.rsi?.toFixed(1) || '--'} sub="Momentum" />
                        <MetricCard title="MACD" value={market.macd?.toFixed(4) || '--'} sub="Trend" />
                        <MetricCard title="ATR" value={market.atr?.toFixed(2) || '--'} sub="Volatility" />
                        <MetricCard title="Margin Free" value={`$${data?.margin_free?.toFixed(0)}`} sub="Liquidity" />
                    </div>

                    {/* Mini Chart Area */}
                    <div className="glass-card p-6 flex-1 min-h-[350px] flex flex-col">
                        <h3 className="text-slate-400 text-sm font-medium mb-4 flex justify-between">
                            <span>Market Technicals ({data?.symbol || '---'})</span>
                            <span className="text-xs text-slate-600">Last 100 Candles</span>
                        </h3>

                        <div className="flex-1 w-full relative">
                            {history.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={history}>
                                        <defs>
                                            <linearGradient id="colorPriceMini" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <XAxis dataKey="time" hide={true} />
                                        <YAxis domain={['auto', 'auto']} hide={true} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#fff' }}
                                            itemStyle={{ color: '#94a3b8' }}
                                        />
                                        <Area
                                            type="monotone"
                                            dataKey="close"
                                            stroke="#3b82f6"
                                            fillOpacity={1}
                                            fill="url(#colorPriceMini)"
                                            strokeWidth={2}
                                            isAnimationActive={false}
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-full flex items-center justify-center text-slate-500 border border-dashed border-slate-700 rounded-lg">
                                    No Chart Data Yet
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

// Helper Components
const Stat = ({ label, value, color = "text-white" }) => (
    <div>
        <div className="text-xs text-slate-500 mb-0.5">{label}</div>
        <div className={`font-mono font-medium ${color}`}>{value ?? '--'}</div>
    </div>
);

const MetricCard = ({ title, value, sub }) => (
    <div className="glass-card p-4 hover:bg-slate-800/50 transition-colors">
        <div className="text-slate-500 text-xs mb-1">{title}</div>
        <div className="text-2xl font-bold text-white mb-1">{value}</div>
        <div className="text-xs text-blue-400">{sub}</div>
    </div>
);

const TrendCompass = ({ d1, h4, m15 }) => {
    const getIcon = (trend) => {
        if (!trend) return <span className="text-slate-600">-</span>;
        if (trend.includes("Bullish")) return <TrendingUp className="w-4 h-4 text-green-400" />;
        if (trend.includes("Bearish")) return <TrendingUp className="w-4 h-4 text-red-400 transform rotate-180" />;
        return <span className="text-slate-400">-</span>;
    };

    return (
        <div className="glass-card p-4 flex flex-col justify-center gap-3">
            <div className="text-[10px] text-slate-500 uppercase tracking-widest text-center">Trend Compass</div>
            <div className="flex justify-between items-center px-2">
                <div className="flex flex-col items-center">
                    <span className="text-xs text-slate-400 mb-1">D1</span>
                    {getIcon(d1)}
                </div>
                <div className="w-px h-8 bg-slate-800"></div>
                <div className="flex flex-col items-center">
                    <span className="text-xs text-slate-400 mb-1">H4</span>
                    {getIcon(h4)}
                </div>
                <div className="w-px h-8 bg-slate-800"></div>
                <div className="flex flex-col items-center">
                    <span className="text-xs text-slate-400 mb-1">M15</span>
                    {getIcon(m15)}
                </div>
            </div>
        </div>
    );
};

const MetricCardSmall = ({ icon, label, value, isCurrency, highlight }) => (
    <div className={`glass-card px-4 py-3 flex items-center gap-3 ${highlight ? 'border-blue-500/30 bg-blue-500/5' : ''}`}>
        <div className="p-2 bg-slate-800 rounded-lg">
            {React.cloneElement(icon, { size: 18 })}
        </div>
        <div>
            <div className="text-[10px] text-slate-400 uppercase tracking-wider">{label}</div>
            <div className={`text-lg font-bold font-mono ${highlight ? 'text-blue-400' : 'text-white'}`}>
                {isCurrency ? `$${value?.toFixed(2) || '0.00'}` : value}
            </div>
        </div>
    </div>
);

export default Cockpit;
