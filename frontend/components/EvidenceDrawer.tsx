"use client";

import React, { useState, useMemo } from "react";
import {
    ChevronDown,
    ChevronUp,
    Code2,
    Table2,
    BookOpen,
    BarChart2,
} from "lucide-react";
import {
    LineChart,
    Line,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";
import { Evidence } from "@/lib/types";
import { useTheme } from "@/lib/theme-context";

interface EvidenceDrawerProps {
    evidence: Evidence;
    intent: "SQL" | "VECTOR" | "BOTH" | "FOLLOWUP";
}

// Detect if a column name looks like a date
function isDateColumn(name: string): boolean {
    return /date|week|month|year|time|period/i.test(name);
}

// Detect if a column is an ID — IDs appear in tables but never in charts
function isIdColumn(name: string): boolean {
    return /\b(id|_id|emp_id|record_id|timesheet_id|employee_id|user_id)\b/i.test(name);
}

// Detect if a value looks numeric
function isNumeric(val: unknown): boolean {
    return typeof val === "number" || (typeof val === "string" && !isNaN(Number(val)));
}

// Build recharts-compatible data from columns + rows
function buildChartData(
    columns: string[],
    rows: (string | number | boolean | null)[][]
): { data: Record<string, unknown>[]; labelKey: string; valueKeys: string[] } | null {
    if (!columns || !rows || rows.length === 0) return null;

    // 1. Try to find a date-like column first, then fall back to first non-numeric column
    let labelIdx = columns.findIndex(isDateColumn);
    if (labelIdx < 0) {
        labelIdx = columns.findIndex(
            (_, i) => !rows.every((r) => isNumeric(r[i]))
        );
    }

    // Exclude ID columns and the label column from chart values
    const valueIdxs = columns
        .map((c, i) => i)
        .filter((i) =>
            i !== labelIdx &&
            !isIdColumn(columns[i]) &&
            rows.some((r) => isNumeric(r[i]))
        );

    if (valueIdxs.length === 0) return null;

    const labelKey = labelIdx >= 0 ? columns[labelIdx] : columns[0];
    const effectiveLabelIdx = labelIdx >= 0 ? labelIdx : 0;

    const data = rows.map((row) => {
        const entry: Record<string, unknown> = { [labelKey]: String(row[effectiveLabelIdx]) };
        valueIdxs.forEach((vi) => {
            entry[columns[vi]] = Number(row[vi]);
        });
        return entry;
    });

    return { data, labelKey, valueKeys: valueIdxs.map((i) => columns[i]) };
}


const CHART_COLORS = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ef4444"];

type Tab = "sql" | "table" | "chart" | "sources";

export default function EvidenceDrawer({ evidence, intent }: EvidenceDrawerProps) {
    const [open, setOpen] = useState(false);
    const { resolved } = useTheme();
    const isDark = resolved === "dark";

    const hasSQL = !!(evidence.sql_query || evidence.sql_table);
    const hasVector = !!(evidence.vector_context || evidence.vector_sources?.length);

    // Pick the best default tab based on what data arrived
    const defaultTab: Tab = hasSQL && evidence.sql_table?.length ? "table"
        : hasSQL && evidence.sql_query ? "sql"
        : "sources";
    const [activeTab, setActiveTab] = useState<Tab>(defaultTab);

    const chartData = useMemo(() => {
        if (!evidence.sql_columns || !evidence.sql_table) return null;
        return buildChartData(evidence.sql_columns, evidence.sql_table);
    }, [evidence.sql_columns, evidence.sql_table]);

    const tabs: { id: Tab; label: string; icon: React.ElementType; show: boolean }[] = (
        [
            { id: "sql" as Tab, label: "SQL Query", icon: Code2, show: hasSQL && !!evidence.sql_query },
            { id: "table" as Tab, label: "Data Table", icon: Table2, show: hasSQL && !!(evidence.sql_table?.length) },
            { id: "chart" as Tab, label: "Chart", icon: BarChart2, show: !!chartData },
            { id: "sources" as Tab, label: "Sources", icon: BookOpen, show: hasVector },
        ] as { id: Tab; label: string; icon: React.ElementType; show: boolean }[]
    ).filter((t) => t.show);

    if (!hasSQL && !hasVector) return null;

    // Recharts tooltip style — adapts to theme
    const tooltipStyle = isDark
        ? { background: "#1f2937", border: "1px solid #374151", borderRadius: 8, fontSize: 11 }
        : { background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 11, color: "#111827" };

    const gridStroke = isDark ? "#374151" : "#e5e7eb";
    const tickFill   = isDark ? "#9ca3af" : "#6b7280";

    return (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700/50 bg-gray-50 dark:bg-gray-900/50 overflow-hidden shadow-md transition-colors duration-200">
            {/* Toggle button */}
            <button
                onClick={() => setOpen((o) => !o)}
                className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors duration-150"
            >
                <span className="flex items-center gap-1.5">
                    {open ? (
                        <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                        <ChevronDown className="w-3.5 h-3.5" />
                    )}
                    {open ? "Hide Evidence" : "View Evidence"}
                </span>
                <span className="flex gap-1.5">
                    {hasSQL && (
                        <span className="px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20 text-[10px]">
                            SQL
                        </span>
                    )}
                    {hasVector && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20 text-[10px]">
                            Vector
                        </span>
                    )}
                </span>
            </button>

            {/* Drawer body */}
            {open && (
                <div className="border-t border-gray-200 dark:border-gray-700/50">
                    {/* Tab bar */}
                    {tabs.length > 1 && (
                        <div className="flex gap-1 px-4 pt-3 pb-0">
                            {tabs.map((tab) => {
                                const Icon = tab.icon;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-t-lg border-b-2 transition-colors duration-150 ${activeTab === tab.id
                                            ? "border-violet-500 text-violet-600 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/10"
                                            : "border-transparent text-gray-500 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                                            }`}
                                    >
                                        <Icon className="w-3 h-3" />
                                        {tab.label}
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    <div className="p-4 space-y-3">
                        {/* SQL Query tab */}
                        {(activeTab === "sql" || tabs.length === 1) && evidence.sql_query && (
                            <div>
                                <p className="text-[10px] uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1.5">
                                    Generated SQL
                                </p>
                                <pre className="bg-gray-100 dark:bg-gray-950 border border-gray-200 dark:border-gray-700/50 rounded-lg p-3 text-xs text-violet-600 dark:text-violet-300 overflow-x-auto whitespace-pre-wrap leading-relaxed font-mono">
                                    {evidence.sql_query}
                                </pre>
                            </div>
                        )}

                        {/* Data Table tab */}
                        {activeTab === "table" &&
                            evidence.sql_columns &&
                            evidence.sql_table && (
                                <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700/50">
                                    <table className="w-full text-xs">
                                        <thead>
                                            <tr className="bg-gray-100 dark:bg-gray-800/80">
                                                {evidence.sql_columns.map((col) => (
                                                    <th
                                                        key={col}
                                                        className="px-3 py-2 text-left font-semibold text-gray-600 dark:text-gray-300 whitespace-nowrap border-b border-gray-200 dark:border-gray-700/50"
                                                    >
                                                        {col}
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {evidence.sql_table.map((row, ri) => (
                                                <tr
                                                    key={ri}
                                                    className="border-b border-gray-100 dark:border-gray-800/50 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
                                                >
                                                    {row.map((cell, ci) => (
                                                        <td
                                                            key={ci}
                                                            className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap"
                                                        >
                                                            {cell === null ? (
                                                                <span className="text-gray-400 dark:text-gray-600 italic">null</span>
                                                            ) : (
                                                                String(cell)
                                                            )}
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                    <p className="text-[10px] text-gray-400 dark:text-gray-600 px-3 py-1.5">
                                        {evidence.sql_table.length} row
                                        {evidence.sql_table.length !== 1 ? "s" : ""}
                                    </p>
                                </div>
                            )}

                        {/* Chart tab */}
                        {activeTab === "chart" && chartData && (
                            <div>
                                <p className="text-[10px] uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-3">
                                    Visualization
                                </p>
                                <div className="bg-white dark:bg-gray-950/50 rounded-lg p-3 border border-gray-200 dark:border-gray-700/50">
                                    <ResponsiveContainer width="100%" height={300}>
                                        {chartData.data.length > 6 ? (
                                            <LineChart data={chartData.data} margin={{ left: 10, right: 10, top: 4, bottom: 50 }}>
                                                <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                                                <XAxis
                                                    dataKey={chartData.labelKey}
                                                    tick={{ fill: tickFill, fontSize: 10 }}
                                                    tickLine={false}
                                                    angle={-35}
                                                    textAnchor="end"
                                                    interval={0}
                                                />
                                                <YAxis tick={{ fill: tickFill, fontSize: 10 }} tickLine={false} width={55} />
                                                <Tooltip contentStyle={tooltipStyle} />
                                                <Legend wrapperStyle={{ fontSize: 11 }} />
                                                {chartData.valueKeys.map((key, i) => (
                                                    <Line
                                                        key={key}
                                                        type="monotone"
                                                        dataKey={key}
                                                        stroke={CHART_COLORS[i % CHART_COLORS.length]}
                                                        strokeWidth={2}
                                                        dot={false}
                                                    />
                                                ))}
                                            </LineChart>
                                        ) : (
                                            <BarChart data={chartData.data} margin={{ left: 10, right: 10, top: 4, bottom: 60 }}>
                                                <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                                                <XAxis
                                                    dataKey={chartData.labelKey}
                                                    tick={{ fill: tickFill, fontSize: 10 }}
                                                    tickLine={false}
                                                    angle={-35}
                                                    textAnchor="end"
                                                    interval={0}
                                                />
                                                <YAxis tick={{ fill: tickFill, fontSize: 10 }} tickLine={false} width={55} />
                                                <Tooltip contentStyle={tooltipStyle} />
                                                <Legend wrapperStyle={{ fontSize: 11 }} />
                                                {chartData.valueKeys.map((key, i) => (
                                                    <Bar
                                                        key={key}
                                                        dataKey={key}
                                                        fill={CHART_COLORS[i % CHART_COLORS.length]}
                                                        radius={[4, 4, 0, 0]}
                                                    />
                                                ))}
                                            </BarChart>
                                        )}
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        )}

                        {/* Sources / Vector tab */}
                        {activeTab === "sources" && hasVector && (
                            <div className="space-y-3">
                                {evidence.vector_sources && evidence.vector_sources.length > 0 && (
                                    <div>
                                        <p className="text-[10px] uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">
                                            Source Documents
                                        </p>
                                        <ul className="space-y-1">
                                            {evidence.vector_sources.map((src) => (
                                                <li
                                                    key={src}
                                                    className="flex items-center gap-2 text-xs text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-lg px-3 py-2"
                                                >
                                                    <BookOpen className="w-3 h-3 flex-shrink-0" />
                                                    <span className="truncate">{src}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {evidence.vector_context && (
                                    <div>
                                        <p className="text-[10px] uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1.5">
                                            Retrieved Context
                                        </p>
                                        <div className="bg-gray-100 dark:bg-gray-950 border border-gray-200 dark:border-gray-700/50 rounded-lg p-3 max-h-48 overflow-y-auto">
                                            {evidence.vector_context.split("---").map((chunk, i) => (
                                                <div
                                                    key={i}
                                                    className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed mb-3 last:mb-0 pb-3 last:pb-0 border-b border-gray-200 dark:border-gray-800 last:border-0"
                                                >
                                                    {chunk.trim()}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
