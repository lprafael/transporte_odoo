/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutos

export class CbdAutoRefreshWidget extends Component {
    static template = "transit_operations.CbdAutoRefreshWidget";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            secondsLeft: Math.floor(REFRESH_INTERVAL_MS / 1000),
            refreshing: false,
            lastRunLabel: null,
        });
        this._nextRunAt = Date.now() + REFRESH_INTERVAL_MS;
        this._timerId = null;

        onMounted(() => {
            this._timerId = window.setInterval(() => {
                if (this.state.refreshing) {
                    return;
                }
                const remainingMs = this._nextRunAt - Date.now();
                if (remainingMs <= 0) {
                    this.triggerAutoRecalculate(false);
                } else {
                    this.state.secondsLeft = Math.ceil(remainingMs / 1000);
                }
            }, 1000);
        });

        onWillUnmount(() => {
            if (this._timerId) {
                window.clearInterval(this._timerId);
                this._timerId = null;
            }
        });
    }

    get formattedCountdown() {
        const total = Math.max(0, this.state.secondsLeft);
        const mins = Math.floor(total / 60);
        const secs = total % 60;
        return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }

    async triggerAutoRecalculate(manual = false) {
        const record = this.props.record;
        if (!record || !record.resId || record.resModel !== "transit.cbd.franja") {
            this._nextRunAt = Date.now() + REFRESH_INTERVAL_MS;
            this.state.secondsLeft = Math.floor(REFRESH_INTERVAL_MS / 1000);
            return;
        }
        if (record.dirty || record.isDirty) {
            // Evita descartar ediciones locales pendientes; reintenta en 30 s
            this._nextRunAt = Date.now() + 30 * 1000;
            this.state.secondsLeft = 30;
            return;
        }

        this.state.refreshing = true;
        try {
            await this.orm.call(
                "transit.cbd.franja",
                "action_recalculate_silent",
                [[record.resId]]
            );
            await record.model.load();
            const now = new Date();
            this.state.lastRunLabel = now.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            });
            if (manual) {
                this.notification.add(
                    "Indicadores CBD e IFO recalculados desde telemetría GPS.",
                    { type: "success" }
                );
            }
        } catch (err) {
            console.warn("Error en auto-recálculo CBD/IFO:", err);
        } finally {
            this.state.refreshing = false;
            this._nextRunAt = Date.now() + REFRESH_INTERVAL_MS;
            this.state.secondsLeft = Math.floor(REFRESH_INTERVAL_MS / 1000);
        }
    }
}

export const cbdAutoRefreshWidget = {
    component: CbdAutoRefreshWidget,
};

registry.category("view_widgets").add("cbd_auto_refresh", cbdAutoRefreshWidget);

