/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TransitRosterBoard extends Component {
    static template = "transit_operations.TransitRosterBoard";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");

        this.state = useState({
            rosterId: null,
            roster: {},
            days: [],
            buses: [],
            drivers: [],
            shifts: [],
            free_drivers_by_day: {},
            viewMode: "bus_matrix", // 'bus_matrix' o 'chronological'
            searchBusQuery: "",
            searchDriverQuery: "",
            selectedBusId: null,
            draggedDriver: null,
            modal: {
                visible: false,
                message: "",
                pendingShiftId: null,
                pendingDriverId: null,
            },
        });

        onWillStart(async () => {
            const ctx = this.props.action && this.props.action.context ? this.props.action.context : {};
            const rosterId = ctx.active_roster_id || ctx.active_id || false;
            await this.loadData(rosterId);
        });
    }

    async loadData(rosterId) {
        try {
            const data = await this.orm.call(
                "transit.driver.roster",
                "get_roster_board_data",
                [rosterId || false]
            );
            if (data.error) {
                this.notification.add(data.error, { type: "danger" });
                return;
            }
            this.state.rosterId = data.roster.id;
            this.state.roster = data.roster;
            this.state.days = data.days;
            this.state.buses = data.buses;
            this.state.drivers = data.drivers;
            this.state.shifts = data.shifts;
            this.state.free_drivers_by_day = data.free_drivers_by_day;
        } catch (err) {
            console.error("Error al cargar datos del cuadrante:", err);
            this.notification.add("Error al conectar con el servidor.", { type: "danger" });
        }
    }

    // =========================================================================
    // Getters y Filtros
    // =========================================================================
    get filteredBuses() {
        const q = (this.state.searchBusQuery || "").toLowerCase().trim();
        if (!q) return this.state.buses;
        return this.state.buses.filter(
            (b) =>
                (b.name && b.name.toLowerCase().includes(q)) ||
                (b.internal_number && b.internal_number.toString().includes(q)) ||
                (b.license_plate && b.license_plate.toLowerCase().includes(q))
        );
    }

    get displayBuses() {
        if (this.state.selectedBusId) {
            return this.state.buses.filter((b) => b.id === this.state.selectedBusId);
        }
        return this.filteredBuses;
    }

    get filteredDrivers() {
        const q = (this.state.searchDriverQuery || "").toLowerCase().trim();
        if (!q) return this.state.drivers;
        return this.state.drivers.filter(
            (d) =>
                (d.name && d.name.toLowerCase().includes(q)) ||
                (d.driver_code && d.driver_code.toLowerCase().includes(q))
        );
    }

    get chronologicalTimeSlots() {
        const slotsSet = new Set();
        this.state.shifts.forEach((s) => {
            if (s.start_time_str) {
                slotsSet.add(s.start_time_str);
            }
        });
        return Array.from(slotsSet).sort();
    }

    getShiftsForBusAndDay(busId, dateStr) {
        return this.state.shifts.filter(
            (s) => s.vehicle_id === busId && s.date === dateStr
        ).sort((a, b) => a.start_time - b.start_time);
    }

    getShiftsForSlotAndDay(timeSlot, dateStr) {
        return this.state.shifts.filter(
            (s) => s.start_time_str === timeSlot && s.date === dateStr
        );
    }

    getShiftPillClasses(shift) {
        const classes = [`direction_${shift.direction}`];
        if (shift.state === "conflict") {
            classes.push("state_conflict");
        }
        return classes.join(" ");
    }

    getDriverHoursClass(totalHours) {
        if (totalHours > 48.0) return "o_hours_danger";
        if (totalHours > 40.0) return "o_hours_warning";
        return "o_hours_normal";
    }

    // =========================================================================
    // Manejo de Interacción y Vistas
    // =========================================================================
    setViewMode(mode) {
        this.state.viewMode = mode;
    }

    onSelectBus(busId) {
        if (this.state.selectedBusId === busId) {
            this.state.selectedBusId = null; // deseleccionar
        } else {
            this.state.selectedBusId = busId;
        }
    }

    // =========================================================================
    // Drag & Drop HTML5
    // =========================================================================
    onDragStartDriver(ev, driver) {
        this.state.draggedDriver = driver;
        try {
            ev.dataTransfer.setData("application/json", JSON.stringify(driver));
            ev.dataTransfer.setData("text/plain", driver.name || "");
        } catch (e) {
            console.error("Error setting dataTransfer:", e);
        }
        ev.dataTransfer.effectAllowed = "all";
        if (ev.currentTarget) {
            ev.currentTarget.classList.add("dragging");
        }
    }

    onDragEndDriver(ev) {
        if (ev.currentTarget) {
            ev.currentTarget.classList.remove("dragging");
        }
    }

    onDragOverCell(ev) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "copy";
        if (ev.currentTarget) {
            ev.currentTarget.classList.add("drag_over_cell");
        }
    }

    onDragLeaveCell(ev) {
        if (ev.currentTarget) {
            ev.currentTarget.classList.remove("drag_over_cell");
        }
    }

    async onDropOnCell(ev, busId, dateStr) {
        ev.preventDefault();
        if (ev.currentTarget) {
            ev.currentTarget.classList.remove("drag_over_cell");
        }

        let driver = this.state.draggedDriver;
        if (!driver) {
            try {
                const dataStr = ev.dataTransfer.getData("application/json");
                if (dataStr) {
                    driver = JSON.parse(dataStr);
                }
            } catch (e) {
                console.error("Error al parsear conductor drag:", e);
            }
        }

        if (!driver || !driver.id) {
            return;
        }

        await this.quickAssignOrCreateShift(busId, dateStr, driver.id, false);
    }

    async quickAssignOrCreateShift(busId, dateStr, driverId, force = false) {
        try {
            const res = await this.orm.call(
                "transit.driver.roster",
                "rpc_quick_assign_or_create_shift",
                [this.state.rosterId, busId, dateStr, driverId, force]
            );

            if (res.conflict) {
                this.state.modal = {
                    visible: true,
                    message: res.message,
                    pendingShiftId: null,
                    pendingDriverId: driverId,
                    pendingCell: res.pendingCell,
                };
                return;
            }

            if (res.success) {
                this.notification.add("Turno asignado correctamente.", { type: "success" });
                if (res.warning) {
                    this.notification.add(res.warning, { type: "warning", sticky: true });
                }
                await this.loadData(this.state.rosterId);
            } else {
                this.notification.add(res.message || "No se pudo asignar el chofer.", { type: "danger" });
            }
        } catch (err) {
            console.error("Error al asignar chofer a la celda:", err);
            this.notification.add("Ocurrió un error al asignar el chofer.", { type: "danger" });
        }
    }

    onDragOverShift(ev, shift) {
        ev.preventDefault();
        ev.stopPropagation();
        ev.dataTransfer.dropEffect = "copy";
        ev.currentTarget.classList.add("drag_over");
    }

    onDragLeaveShift(ev, shift) {
        ev.currentTarget.classList.remove("drag_over");
    }

    async onDropOnShift(ev, shift) {
        ev.preventDefault();
        ev.stopPropagation();
        ev.currentTarget.classList.remove("drag_over");

        let driver = this.state.draggedDriver;
        if (!driver) {
            try {
                const dataStr = ev.dataTransfer.getData("application/json");
                if (dataStr) {
                    driver = JSON.parse(dataStr);
                }
            } catch (e) {
                console.error("Error al parsear conductor drag:", e);
            }
        }

        if (!driver || !driver.id) {
            return;
        }

        await this.assignDriverToShift(shift.id, driver.id, false);
    }

    async assignDriverToShift(shiftId, driverId, force = false) {
        try {
            const res = await this.orm.call(
                "transit.driver.roster",
                "rpc_assign_driver",
                [shiftId, driverId, force]
            );

            if (res.conflict) {
                // Mostrar Modal de Conflicto
                this.state.modal = {
                    visible: true,
                    message: res.message,
                    pendingShiftId: shiftId,
                    pendingDriverId: driverId,
                    pendingCell: null,
                };
                return;
            }

            if (res.success) {
                this.notification.add("Conductor asignado con éxito.", { type: "success" });
                if (res.warning) {
                    this.notification.add(res.warning, { type: "warning", sticky: true });
                }
                // Recargar datos en tiempo real
                await this.loadData(this.state.rosterId);
            } else {
                this.notification.add(res.message || "No se pudo asignar el conductor.", { type: "danger" });
            }
        } catch (err) {
            console.error("Error al asignar chofer:", err);
            this.notification.add("Ocurrió un error al asignar el chofer.", { type: "danger" });
        }
    }

    async onUnassignDriver(shiftId) {
        try {
            const res = await this.orm.call(
                "transit.driver.roster",
                "rpc_unassign_driver",
                [shiftId]
            );
            if (res.success) {
                this.notification.add("Conductor desasignado del turno.", { type: "info" });
                await this.loadData(this.state.rosterId);
            }
        } catch (err) {
            console.error("Error al desasignar:", err);
        }
    }

    onCloseModal() {
        this.state.modal.visible = false;
        this.state.modal.pendingShiftId = null;
        this.state.modal.pendingDriverId = null;
        this.state.modal.pendingCell = null;
    }

    async onForceAssign() {
        const { pendingShiftId, pendingDriverId, pendingCell } = this.state.modal;
        this.onCloseModal();
        if (pendingShiftId && pendingDriverId) {
            await this.assignDriverToShift(pendingShiftId, pendingDriverId, true);
        } else if (pendingCell && pendingDriverId) {
            await this.quickAssignOrCreateShift(
                pendingCell.vehicleId,
                pendingCell.dateStr,
                pendingDriverId,
                true
            );
        }
    }

    // =========================================================================
    // Botones de Acción
    // =========================================================================
    async onLoadOperationalSchedule() {
        try {
            await this.orm.call(
                "transit.driver.roster",
                "action_load_from_operational_schedules",
                [[this.state.rosterId]]
            );
            this.notification.add("Programación operativa sincronizada.", { type: "success" });
            await this.loadData(this.state.rosterId);
        } catch (err) {
            console.error(err);
        }
    }

    async onDuplicateNextWeek() {
        try {
            const resAction = await this.orm.call(
                "transit.driver.roster",
                "action_duplicate_next_week",
                [[this.state.rosterId]]
            );
            this.notification.add("Cuadrante duplicado para la semana siguiente.", { type: "success" });
            if (resAction && resAction.res_id) {
                this.state.rosterId = resAction.res_id;
                await this.loadData(resAction.res_id);
            }
        } catch (err) {
            console.error(err);
        }
    }

    async onExportExcel() {
        try {
            const action = await this.orm.call(
                "transit.driver.roster",
                "action_export_excel",
                [[this.state.rosterId]]
            );
            if (action && action.url) {
                window.open(action.url, "_blank");
            }
        } catch (err) {
            console.error(err);
        }
    }

    async onPrintPdf() {
        await this.actionService.doAction(
            "transit_operations.action_report_transit_driver_roster",
            {
                additionalContext: { active_ids: [this.state.rosterId] },
            }
        );
    }

    async onConfirmAndSync() {
        try {
            await this.orm.call(
                "transit.driver.roster",
                "action_confirm",
                [[this.state.rosterId]]
            );
            this.notification.add("¡Cuadrante confirmado y despachos sincronizados!", { type: "success" });
            await this.loadData(this.state.rosterId);
        } catch (err) {
            console.error(err);
        }
    }
}

registry.category("actions").add("transit_roster_board", TransitRosterBoard);
