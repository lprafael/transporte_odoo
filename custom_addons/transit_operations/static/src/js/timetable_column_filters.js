/** @odoo-module **/

/**
 * Filtros Interactivos por Columna en Cabecera de Tablas (Estilo Excel / DataTables)
 * Módulo: transit_operations (Odoo 18)
 */

function normalizeText(text) {
    if (!text) return "";
    return text
        .toString()
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim();
}

function applyFilters(table) {
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    if (!thead || !tbody) return;

    const filterInputs = thead.querySelectorAll(".o_transit_col_filter_input");
    const activeFilters = [];

    filterInputs.forEach((input) => {
        const val = normalizeText(input.value);
        const colIndex = parseInt(input.dataset.colIndex, 10);
        if (val) {
            input.classList.add("has_value");
            activeFilters.push({ colIndex, val });
        } else {
            input.classList.remove("has_value");
        }
    });

    const rows = tbody.querySelectorAll("tr.o_data_row");
    let visibleCount = 0;

    rows.forEach((row) => {
        let matches = true;
        for (const f of activeFilters) {
            const cell = row.children[f.colIndex];
            if (!cell) {
                matches = false;
                break;
            }
            const cellText = normalizeText(cell.innerText || cell.textContent);
            if (!cellText.includes(f.val)) {
                matches = false;
                break;
            }
        }

        if (matches) {
            row.style.display = "";
            visibleCount++;
        } else {
            row.style.display = "none";
        }
    });

    // Actualizar badge de contador si existe
    let badge = table.parentElement.querySelector(".o_transit_filter_counter_badge");
    if (!badge) {
        badge = document.createElement("span");
        badge.className = "o_transit_filter_counter_badge";
        const controlPanel = document.querySelector(".o_control_panel_actions") || table.parentElement;
        if (controlPanel) {
            controlPanel.appendChild(badge);
        }
    }
    if (activeFilters.length > 0) {
        badge.style.display = "inline-block";
        badge.innerText = `🔍 Filtrados: ${visibleCount} de ${rows.length} registros`;
    } else {
        badge.style.display = "none";
    }
}

function initTableFilters(table) {
    if (table.dataset.transitFiltersInitialized === "true") return;

    const thead = table.querySelector("thead");
    if (!thead) return;

    const headerRow = thead.querySelector("tr:not(.o_transit_header_filters)");
    if (!headerRow) return;

    // Verificar si es la tabla de timetable o tabla de operaciones
    const isTimetable = table.closest(".o_transit_timetable_list") || 
                        document.querySelector(".o_action[data-action-id*='timetable']") ||
                        headerRow.textContent.includes("Servicio") && headerRow.textContent.includes("Salida");

    // Si la tabla ya tiene la fila de filtros, omitir creación
    let filterRow = thead.querySelector(".o_transit_header_filters");
    if (filterRow) return;

    table.dataset.transitFiltersInitialized = "true";

    filterRow = document.createElement("tr");
    filterRow.className = "o_transit_header_filters";

    const thElements = Array.from(headerRow.children);

    thElements.forEach((th, index) => {
        const filterTh = document.createElement("th");
        const thText = (th.innerText || th.textContent).trim();
        const isSelector = th.classList.contains("o_list_record_selector") || th.querySelector("input[type='checkbox']");

        if (isSelector) {
            filterTh.innerHTML = `
                <div class="d-flex justify-content-center">
                    <button type="button" class="o_transit_reset_all_btn" title="Limpiar todos los filtros de cabecera">
                        <i class="fa fa-eraser"></i>
                    </button>
                </div>
            `;
            const resetBtn = filterTh.querySelector(".o_transit_reset_all_btn");
            if (resetBtn) {
                resetBtn.addEventListener("click", (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const inputs = table.querySelectorAll(".o_transit_col_filter_input");
                    inputs.forEach((inp) => (inp.value = ""));
                    applyFilters(table);
                });
            }
        } else if (thText) {
            filterTh.innerHTML = `
                <div class="o_transit_col_filter_wrapper">
                    <input type="text" 
                           class="o_transit_col_filter_input" 
                           placeholder="Filtrar ${thText}..." 
                           title="Filtrar por ${thText}" 
                           data-col-index="${index}" />
                    <button type="button" class="o_transit_clear_col_btn" title="Borrar filtro">×</button>
                </div>
            `;

            const input = filterTh.querySelector(".o_transit_col_filter_input");
            const clearBtn = filterTh.querySelector(".o_transit_clear_col_btn");

            input.addEventListener("input", () => {
                applyFilters(table);
            });

            input.addEventListener("click", (e) => {
                e.stopPropagation();
            });

            clearBtn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                input.value = "";
                applyFilters(table);
                input.focus();
            });
        }

        filterRow.appendChild(filterTh);
    });

    thead.appendChild(filterRow);

    // Observar cambios en el tbody (por ordenación, paginación, etc.)
    const tbody = table.querySelector("tbody");
    if (tbody) {
        const tbodyObserver = new MutationObserver(() => {
            applyFilters(table);
        });
        tbodyObserver.observe(tbody, { childList: true });
    }
}

// Observador global para inyectar filtros en cada tabla de lista renderizada
function scanAndInitTables() {
    const tables = document.querySelectorAll(".o_list_table");
    tables.forEach((tbl) => {
        // Inicializar si contiene columnas de transporte o clase específica
        const headers = tbl.querySelector("thead tr");
        if (headers) {
            const txt = headers.textContent;
            if (txt.includes("Servicio") || txt.includes("Ruta") || txt.includes("Salida") || tbl.closest(".o_transit_timetable_list")) {
                initTableFilters(tbl);
            }
        }
    });
}

// Iniciar al cargar el DOM y con MutationObserver
if (typeof document !== "undefined") {
    const observer = new MutationObserver((mutations) => {
        let shouldCheck = false;
        for (const mut of mutations) {
            if (mut.addedNodes.length > 0) {
                shouldCheck = true;
                break;
            }
        }
        if (shouldCheck) {
            scanAndInitTables();
        }
    });

    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
        scanAndInitTables();
    } else {
        document.addEventListener("DOMContentLoaded", () => {
            observer.observe(document.body, { childList: true, subtree: true });
            scanAndInitTables();
        });
    }
}
