import { LayoutDashboard, BrainCircuit, Activity, Wallet, Dna, Menu, X } from 'lucide-react';

const Sidebar = ({ activePage, setActivePage, mobileOpen, setMobileOpen }) => {
    const menuItems = [
        { id: 'cockpit', label: 'Cockpit', icon: LayoutDashboard },
        { id: 'cortex', label: 'Cortex', icon: BrainCircuit },
        { id: 'market', label: 'Deep Market', icon: Activity },
        { id: 'ledger', label: 'Ledger', icon: Wallet },
        { id: 'darwin', label: 'Darwin Swarm', icon: Dna },
    ];

    const handleNav = (id) => {
        setActivePage(id);
        setMobileOpen(false); // Close sidebar on mobile after navigation
    };

    return (
        <>
            {/* Mobile Hamburger Button */}
            <button
                onClick={() => setMobileOpen(!mobileOpen)}
                className="lg:hidden fixed top-4 left-4 z-[60] p-2 bg-fintech-card border border-fintech-border rounded-lg text-slate-300 hover:text-white transition-colors"
                aria-label="Toggle menu"
            >
                {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            {/* Mobile Overlay */}
            {mobileOpen && (
                <div
                    className="lg:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* Sidebar */}
            <div className={`
                h-screen w-64 bg-fintech-card border-r border-fintech-border flex flex-col fixed left-0 top-0 z-50
                transition-transform duration-300 ease-in-out
                ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
                lg:translate-x-0
            `}>
                <div className="p-6 flex items-center gap-3 border-b border-fintech-border">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/20">
                        <Activity className="w-5 h-5 text-white" />
                    </div>
                    <h1 className="text-xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                        SENTIENT
                    </h1>
                </div>

                <nav className="flex-1 p-4 space-y-2">
                    {menuItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = activePage === item.id;
                        return (
                            <button
                                key={item.id}
                                onClick={() => handleNav(item.id)}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${isActive
                                    ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20 shadow-lg shadow-blue-500/10'
                                    : 'text-slate-400 hover:bg-fintech-border/50 hover:text-white'
                                    }`}
                            >
                                <Icon className={`w-5 h-5 ${isActive ? 'text-blue-400' : 'text-slate-500 group-hover:text-white'}`} />
                                <span className="font-medium">{item.label}</span>
                                {isActive && (
                                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                                )}
                            </button>
                        );
                    })}
                </nav>

                <div className="p-4 border-t border-fintech-border">
                    <div className="flex items-center gap-2 text-xs text-slate-500 px-4">
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                        SYSTEM ONLINE
                    </div>
                </div>
            </div>
        </>
    );
};

export default Sidebar;
