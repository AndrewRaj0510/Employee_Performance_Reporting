"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Database, FileText, Layers, Clock, GitBranch } from "lucide-react";

interface InsightCardProps {
    text: string;
    intent: "SQL" | "VECTOR" | "BOTH" | "FOLLOWUP";
    latency: number;
}

const intentConfig = {
    SQL: {
        icon: Database,
        label: "SQL",
        color: "text-blue-600 dark:text-blue-400",
        bg: "bg-blue-50 dark:bg-blue-500/10",
        border: "border-blue-200 dark:border-blue-500/30",
    },
    VECTOR: {
        icon: FileText,
        label: "Vector",
        color: "text-emerald-600 dark:text-emerald-400",
        bg: "bg-emerald-50 dark:bg-emerald-500/10",
        border: "border-emerald-200 dark:border-emerald-500/30",
    },
    BOTH: {
        icon: Layers,
        label: "Hybrid",
        color: "text-violet-600 dark:text-violet-400",
        bg: "bg-violet-50 dark:bg-violet-500/10",
        border: "border-violet-200 dark:border-violet-500/30",
    },
    FOLLOWUP: {
        icon: GitBranch,
        label: "Follow-up",
        color: "text-amber-600 dark:text-amber-400",
        bg: "bg-amber-50 dark:bg-amber-500/10",
        border: "border-amber-200 dark:border-amber-500/30",
    },
};

// Custom table components so markdown tables get proper styling
const markdownComponents = {
    // Wrap table in a scrollable container
    table: ({ children }: React.HTMLAttributes<HTMLTableElement>) => (
        <div className="overflow-x-auto my-3 rounded-lg border border-gray-200 dark:border-gray-700/60 shadow-sm">
            <table className="w-full text-sm border-collapse">{children}</table>
        </div>
    ),
    thead: ({ children }: React.HTMLAttributes<HTMLTableSectionElement>) => (
        <thead className="bg-gray-100 dark:bg-gray-800/90 sticky top-0">{children}</thead>
    ),
    tbody: ({ children }: React.HTMLAttributes<HTMLTableSectionElement>) => (
        <tbody>{children}</tbody>
    ),
    tr: ({ children, ...props }: React.HTMLAttributes<HTMLTableRowElement>) => (
        <tr
            className="border-b border-gray-200 dark:border-gray-700/40 even:bg-gray-50 dark:even:bg-gray-800/30 hover:bg-violet-50 dark:hover:bg-violet-500/10 transition-colors duration-100"
            {...props}
        >
            {children}
        </tr>
    ),
    th: ({ children }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
        <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider whitespace-nowrap border-b border-gray-200 dark:border-gray-700/60">
            {children}
        </th>
    ),
    td: ({ children }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
        <td className="px-4 py-2 text-sm text-gray-700 dark:text-gray-200 whitespace-nowrap">
            {children}
        </td>
    ),
};

export default function InsightCard({ text, intent, latency }: InsightCardProps) {
    const cfg = intentConfig[intent] ?? intentConfig["SQL"];
    const Icon = cfg.icon;

    return (
        <div className="bg-white dark:bg-gray-800/60 rounded-2xl rounded-tl-sm border border-gray-200 dark:border-gray-700/50 overflow-hidden shadow-lg transition-colors duration-200">
            {/* Badge row */}
            <div className="flex items-center gap-2 px-4 pt-3 pb-2">
                <span
                    className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${cfg.bg} ${cfg.border} ${cfg.color}`}
                >
                    <Icon className="w-3 h-3" />
                    {cfg.label}
                </span>
                <span className="ml-auto flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500">
                    <Clock className="w-3 h-3" />
                    {latency}s
                </span>
            </div>

            {/* Markdown content */}
            <div className="px-4 pb-4">
                <div className="prose prose-gray dark:prose-invert prose-sm max-w-none
          prose-p:text-gray-700 dark:prose-p:text-gray-200 prose-p:leading-relaxed
          prose-headings:text-gray-900 dark:prose-headings:text-white prose-headings:font-semibold
          prose-strong:text-gray-900 dark:prose-strong:text-white
          prose-code:text-violet-600 dark:prose-code:text-violet-300 prose-code:bg-gray-100 dark:prose-code:bg-gray-900 prose-code:px-1 prose-code:py-0.5 prose-code:rounded
          prose-pre:bg-gray-100 dark:prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-200 dark:prose-pre:border-gray-700
          prose-ul:text-gray-700 dark:prose-ul:text-gray-200 prose-li:text-gray-700 dark:prose-li:text-gray-200
          prose-a:text-violet-600 dark:prose-a:text-violet-400
          prose-table:w-full">
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={markdownComponents}
                    >
                        {text}
                    </ReactMarkdown>
                </div>
            </div>
        </div>
    );
}
