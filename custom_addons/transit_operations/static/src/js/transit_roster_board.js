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
            viewMode: "cuadrillas", // 'cuadrillas' (Programación Operativa), 'bus_matrix', o 'chronological'
            selectedDayIndex: 0,    // Lunes por defecto (0..6) o null para todos
            selectedServiceFilter: "ALL", // 'ALL', 'E1', 'E2', 'E3', etc.
            searchCuadrillaQuery: "",
            searchBusQuery: "",
            searchDriverQuery: "",
            selectedBusId: null,
            draggedBus: null,
            draggedDriver: null,
            draggedType: null, // 'bus' | 'driver'
            modal: {
                visible: false,
                message: "",
                pendingShiftId: null,
                pendingDriverId: null,
                pendingBusId: null,
                pendingCell: null,
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

            // Si no hay día seleccionado válido, seleccionar el primer día
            if (this.state.selectedDayIndex === null && data.days && data.days.length > 0) {
                this.state.selectedDayIndex = 0;
            }
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

    get availableServices() {
        const servicesSet = new Set();
        (this.state.shifts || []).forEach((s) => {
            if (s.service_code) {
                servicesSet.add(s.service_code);
            }
        });
        return Array.from(servicesSet).sort();
    }

    get selectedDayObj() {
        if (this.state.selectedDayIndex === null) {
            return { name: "Todos los Días de la Semana", display_date: "Semana Completa" };
        }
        return (this.state.days || []).find((d) => d.index === this.state.selectedDayIndex) || {
            name: "Día " + this.state.selectedDayIndex,
            display_date: "",
        };
    }

    get cuadrillasForDisplay() {
        let list = this.state.shifts || [];

        // Filtro por Día
        if (this.state.selectedDayIndex !== null) {
            list = list.filter((s) => s.day_index === this.state.selectedDayIndex);
        }

        // Filtro por Servicio / Línea
        if (this.state.selectedServiceFilter && this.state.selectedServiceFilter !== "ALL") {
            list = list.filter((s) => s.service_code === this.state.selectedServiceFilter);
        }

        // Buscador de Cuadrillas
        const q = (this.state.searchCuadrillaQuery || "").toLowerCase().trim();
        if (q) {
            list = list.filter(
                (s) =>
                    (s.start_time_str && s.start_time_str.toLowerCase().includes(q)) ||
                    (s.service_code && s.service_code.toLowerCase().includes(q)) ||
                    (s.route_name && s.route_name.toLowerCase().includes(q)) ||
                    (s.bus_internal_number && s.bus_internal_number.toString().toLowerCase().includes(q)) ||
                    (s.license_plate && s.license_plate.toLowerCase().includes(q)) ||
                    (s.driver_name && s.driver_name.toLowerCase().includes(q))
            );
        }

        return list.slice().sort((a, b) => (a.start_time || 0) - (b.start_time || 0));
    }

    getDayStats(dayIndex) {
        const dayShifts = (this.state.shifts || []).filter((s) => s.day_index === dayIndex);
        const total = dayShifts.length;
        const withBus = dayShifts.filter((s) => s.vehicle_id).length;
        const withDriver = dayShifts.filter((s) => s.driver_id).length;
        const complete = dayShifts.filter((s) => s.vehicle_id && s.driver_id).length;
        return {
            total,
            withBus,
            withDriver,
            complete,
            percentage: total ? Math.round((complete / total) * 100) : 0,
        };
    }

    get chronologicalTimeSlots() {
        const slotsSet = new Set();
        (this.state.shifts || []).forEach((s) => {
            if (s.start_time_str) {
                slotsSet.add(s.start_time_str);
            }
        });
        return Array.from(slotsSet).sort();
    }

    getShiftsForBusAndDay(busId, dateStr) {
        return (this.state.shifts || [])
            .filter((s) => s.vehicle_id === busId && s.date === dateStr)
            .sort((a, b) => a.start_time - b.start_time);
    }

    getShiftsForSlotAndDay(timeSlot, dateStr) {
        return (this.state.shifts || []).filter(
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

    selectDay(dayIndex) {
        this.state.selectedDayIndex = dayIndex;
    }

    selectServiceFilter(code) {
        this.state.selectedServiceFilter = code;
    }

    onSelectBus(busId) {
        if (this.state.selectedBusId === busId) {
            this.state.selectedBusId = null; // deseleccionar
        } else {
            this.state.selectedBusId = busId;
        }
    }

    // =========================================================================
    // Drag & Drop HTML5 para BUSES
    // =========================================================================
    onDragStartBus(ev, bus) {
        this.state.draggedBus = bus;
        this.state.draggedDriver = null;
        this.state.draggedType = "bus";
        try {
            ev.dataTransfer.setData("application/json", JSON.stringify({ type: "bus", data: bus }));
            ev.dataTransfer.setData("text/plain", "bus:" + bus.id);
        } catch (e) {
            console.error("Error setting dataTransfer bus:", e);
        }
        ev.dataTransfer.effectAllowed = "all";
        if (ev.currentTarget) {
            ev.currentTarget.classList.add("dragging");
        }
    }

    onDragEndBus(ev) {
        if (ev.currentTarget) {
            ev.currentTarget.classList.remove("dragging");
        }
        this.state.draggedBus = null;
        this.state.draggedType = null;
    }

    // =========================================================================
    // Drag & Drop HTML5 para CHOFERES
    // =========================================================================
    onDragStartDriver(ev, driver) {
        this.state.draggedDriver = driver;
        this.state.draggedBus = null;
        this.state.draggedType = "driver";
        try {
            ev.dataTransfer.setData("application/json", JSON.stringify({ type: "driver", data: driver }));
            ev.dataTransfer.setData("text/plain", "driver:" + driver.id);
        } catch (e) {
            console.error("Error setting dataTransfer driver:", e);
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
        this.state.draggedDriver = null;
        this.state.draggedType = null;
    }

    // =========================================================================
    // Zonas de Drop (Slots de Asignación en Cuadrillas)
    // =========================================================================
    onDragOverSlot(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        ev.dataTransfer.dropEffect = "copy";
        if (ev.currentTarget) {
            ev.currentTarget.classList.add("drag_over");
        }
    }

    onDragLeaveSlot(ev) {
        if (ev.currentTarget) {
            ev.currentTarget.classList.remove("drag_over");
        }
    }

    async onDropBusOnShift(ev, shift) {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.currentTarget) {
            ev.currentTarget.classList.remove("drag_over");
        }

        let bus = this.state.draggedBus;
        if (!bus) {
            try {
                const dataStr = ev.dataTransfer.getData("application/json");
                if (dataStr) {
                    const parsed = JSON.parse(dataStr);
                    if (parsed.type === "bus") bus = parsed.data;
                    else if (!parsed.type && parsed.bus_internal_number) bus = parsed;
                }
            } catch (e) {}
        }

        if (bus && bus.id) {
            await this.assignBusToShift(shift.id, bus.id, false);
        } else {
            this.notification.add("Debes arrastrar un bus desde el panel de Flota.", { type: "warning" });
        }
    }

    async onDropDriverOnShift(ev, shift) {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.currentTarget) {
            ev.currentTarget.classList.remove("drag_over");
        }

        let driver = this.state.draggedDriver;
        if (!driver) {
            try {
                const dataStr = ev.dataTransfer.getData("application/json");
                if (dataStr) {
                    const parsed = JSON.parse(dataStr);
                    if (parsed.type === "driver") driver = parsed.data;
                    else if (!parsed.type && !parsed.bus_internal_number) driver = parsed;
                }
            } catch (e) {}
        }

        if (driver && driver.id) {
            await this.assignDriverToShift(shift.id, driver.id, false);
        } else {
            this.notification.add("Debes arrastrar un conductor desde el panel de Conductores.", { type: "warning" });
        }
    }

    async onDropUnifiedShift(ev, shift) {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.currentTarget) {
            ev.currentTarget.classList.remove("drag_over");
        }

        if (this.state.draggedType === "bus" || this.state.draggedBus) {
            await this.onDropBusOnShift(ev, shift);
        } else if (this.state.draggedType === "driver" || this.state.draggedDriver) {
            await this.onDropDriverOnShift(ev, shift);
        } else {
            // Inspeccionar datos transferidos
            try {
                const dataStr = ev.dataTransfer.getData("application/json");
                if (dataStr) {
                    const parsed = JSON.parse(dataStr);
                    if (parsed.type === "bus" || parsed.bus_internal_number) {
                        this.state.draggedBus = parsed.data || parsed;
                        await this.onDropBusOnShift(ev, shift);
                    } else {
                        this.state.draggedDriver = parsed.data || parsed;
                        await this.onDropDriverOnShift(ev, shift);
                    }
                }
            } catch (e) {
                console.error("Error al determinar drop:", e);
            }
        }
    }

    // =========================================================================
    // Asignación y Desasignación RPC
    // =========================================================================
    async assignBusToShift(shiftId, busId, force = false) {
        try {
            const res = await this.orm.call(
                "transit.driver.roster",
                "rpc_assign_bus",
                [shiftId, busId, force]
            );

            if (res.conflict) {
                this.state.modal = {
                    visible: true,
                    message: res.message,
                    pendingShiftId: shiftId,
                    pendingBusId: busId,
                    pendingDriverId: null,
                    pendingCell: null,
                };
                return;
            }

            if (res.success) {
                this.notification.add("Bus asignado con éxito a la programación operativa.", { type: "success" });
                await this.loadData(this.state.rosterId);
            } else {
                this.notification.add(res.message || "No se pudo asignar el bus.", { type: "danger" });
            }
        } catch (err) {
            console.error("Error al asignar bus:", err);
            this.notification.add("Error al asignar el bus.", { type: "danger" });
        }
    }

    async onUnassignBus(shiftId) {
        try {
            const res = await this.orm.call(
                "transit.driver.roster",
                "rpc_unassign_bus",
                [shiftId]
            );
            if (res.success) {
                this.notification.add("Bus desasignado de la programación.", { type: "info" });
                await this.loadData(this.state.rosterId);
            }
        } catch (err) {
            console.error("Error al desasignar bus:", err);
        }
    }

    async assignDriverToShift(shiftId, driverId, force = false) {
        try {
            const res = await this.orm.call(
                "transit.driver.roster",
                "rpc_assign_driver",
                [shiftId, driverId, force]
            );

            if (res.conflict) {
                this.state.modal = {
                    visible: true,
                    message: res.message,
                    pendingShiftId: shiftId,
                    pendingDriverId: driverId,
                    pendingBusId: null,
                    pendingCell: null,
                };
                return;
            }

            if (res.success) {
                this.notification.add("Conductor asignado con éxito a la programación.", { type: "success" });
                if (res.warning) {
                    this.notification.add(res.warning, { type: "warning", sticky: true });
                }
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
            console.error("Error al desasignar chofer:", err);
        }
    }

    // Matriz Buses x Días
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
                    const parsed = JSON.parse(dataStr);
                    if (parsed.type === "driver") driver = parsed.data;
                    else if (!parsed.type && !parsed.bus_internal_number) driver = parsed;
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
                    pendingBusId: null,
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

    onCloseModal() {
        this.state.modal.visible = false;
        this.state.modal.pendingShiftId = null;
        this.state.modal.pendingDriverId = null;
        this.state.modal.pendingBusId = null;
        this.state.modal.pendingCell = null;
    }

    async onForceAssign() {
        const { pendingShiftId, pendingDriverId, pendingBusId, pendingCell } = this.state.modal;
        this.onCloseModal();

        if (pendingShiftId && pendingBusId) {
            await this.assignBusToShift(pendingShiftId, pendingBusId, true);
        } else if (pendingShiftId && pendingDriverId) {
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
            const res = await this.orm.call(
                "transit.driver.roster",
                "action_load_from_operational_schedules",
                [[this.state.rosterId]]
            );
            this.notification.add("Cuadrillas y programación operativa sincronizada.", { type: "success" });
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
