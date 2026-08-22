import { jsx as _jsx } from "react/jsx-runtime";
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { StatusBadge } from '../components/StatusBadge';
import { Timeline } from '../components/Timeline';
describe('AegisOps UI Components', () => {
    it('renders LoadingState with default message', () => {
        render(_jsx(LoadingState, {}));
        expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
    it('renders ErrorState with message and retry button', () => {
        const onRetry = () => { };
        render(_jsx(ErrorState, { message: "Connection failed", onRetry: onRetry }));
        expect(screen.getByText('Connection failed')).toBeInTheDocument();
        expect(screen.getByText('Retry')).toBeInTheDocument();
    });
    it('renders StatusBadge with correct status text', () => {
        render(_jsx(StatusBadge, { status: "HEALTHY" }));
        expect(screen.getByText('HEALTHY')).toBeInTheDocument();
    });
    it('renders Timeline events correctly', () => {
        const events = [
            { ts: 1724180000, stage: 'RECEIVED', status: 'OK', detail: 'Incident received' },
        ];
        render(_jsx(Timeline, { events: events }));
        expect(screen.getByText('RECEIVED')).toBeInTheDocument();
        expect(screen.getByText('Incident received')).toBeInTheDocument();
    });
});
