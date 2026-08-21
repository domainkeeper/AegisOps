import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function ErrorState({ message, onRetry }) {
    return (_jsxs("div", { className: "error-state", children: [_jsx("strong", { children: "Error:" }), " ", message, onRetry && _jsx("button", { className: "btn", onClick: onRetry, style: { marginLeft: '0.75rem' }, children: "Retry" })] }));
}
