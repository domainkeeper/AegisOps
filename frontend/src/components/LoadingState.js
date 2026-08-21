import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function LoadingState({ message = 'Loading...' }) {
    return (_jsxs("div", { className: "loading-state", children: [_jsx("div", { className: "spinner" }), _jsx("span", { children: message })] }));
}
