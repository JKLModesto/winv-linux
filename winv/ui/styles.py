"""
Definições de estilos CSS para a interface GTK3 do winv-linux.
Design Dark Mode com inspiração Fluent (Windows 11).
"""

CSS_STYLES = """
window.winv-popup {
    background-color: rgba(30, 30, 30, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
}

.header-box {
    padding: 12px 14px 8px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.title-label {
    font-size: 13px;
    font-weight: bold;
    color: #e0e0e0;
}

.clear-btn {
    font-size: 11px;
    color: #a0a0a0;
    background: transparent;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}
.clear-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}

.search-entry {
    background-color: rgba(45, 45, 45, 0.9);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
    margin-top: 6px;
}
.search-entry:focus {
    border-color: #0078d4;
}

.cards-scroller {
    padding: 8px 10px;
}

.card-item {
    background-color: rgba(44, 44, 44, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 8px;
    transition: all 120ms ease;
}
.card-item:hover, .card-item:focus {
    background-color: rgba(58, 58, 58, 0.98);
    border-color: #0078d4;
}

.card-pinned {
    border-left: 3px solid #0078d4;
}

.card-text {
    font-size: 12px;
    color: #f0f0f0;
}

.meta-label {
    font-size: 10px;
    color: #888888;
}

.action-btn {
    background: transparent;
    border: none;
    padding: 4px;
    border-radius: 4px;
    color: #a0a0a0;
}
.action-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: #ffffff;
}
.action-btn.pinned {
    color: #ffffff;
}
.action-btn image {
    -gtk-icon-shadow: none;
}

.tab-bar {
    margin-bottom: 4px;
}
.tab-bar scrolledwindow scrollbar {
    min-width: 0;
    min-height: 0;
    opacity: 0;
}
.tab-btn {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    box-shadow: none;
    transition: border-color 120ms ease, color 120ms ease;
}
.tab-btn:hover {
    background: transparent;
    border-bottom-color: rgba(255, 255, 255, 0.35);
}
.tab-btn.tab-active {
    background: transparent;
    border-bottom: 2px solid #ffffff;
}
.tab-inner {
    padding: 4px 8px 6px 8px;
}
.tab-btn label {
    font-size: 11px;
    font-weight: 500;
    color: #8c8c8c;
}
.tab-btn:hover label {
    color: #ffffff;
}
.tab-btn.tab-active label {
    color: #ffffff;
    font-weight: 600;
}
.tab-btn image {
    opacity: 0.70;
}
.tab-btn:hover image, .tab-btn.tab-active image {
    opacity: 1.0;
}
.tab-btn.tab-dragging {
    opacity: 0.50;
    border-bottom: 2px dashed rgba(255, 255, 255, 0.80);
}
.tab-bar .action-btn {
    background: transparent;
    border: none;
    padding: 4px 6px;
    border-radius: 4px;
    color: #8c8c8c;
    box-shadow: none;
}
.tab-bar .action-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}
.status-label {
    font-size: 10px;
    color: #bdbdbd;
    margin-right: 6px;
}

popover {
    background-color: #2b2b2b;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
}
.popover-box {
    padding: 8px;
}
.popover-title {
    font-size: 11px;
    font-weight: bold;
    color: #d0d0d0;
}
.menu-btn {
    font-size: 12px;
    color: #e0e0e0;
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    box-shadow: none;
}
.menu-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
}
.menu-btn:disabled {
    color: #666666;
}
.danger-btn:hover {
    background-color: rgba(255, 255, 255, 0.14);
    color: #ffffff;
}
.form-label {
    font-size: 11px;
    font-weight: 600;
    color: #cccccc;
    margin-top: 6px;
    margin-bottom: 2px;
}
.error-label {
    font-size: 11px;
    color: #ff6b6b;
    font-weight: 500;
    margin-top: 4px;
}
popover entry, popover entry text {
    color: #ffffff;
}
.unlock-box {
    padding: 30px 20px;
}
.unlock-title {
    font-size: 13px;
    font-weight: bold;
    color: #ffffff;
    margin-top: 8px;
}
.unlock-subtitle {
    font-size: 11px;
    color: #8e8e8e;
    margin-bottom: 12px;
}
.form-btn {
    background-color: rgba(255, 255, 255, 0.08);
    color: #e0e0e0;
    font-size: 12px;
    font-weight: 500;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    padding: 6px 12px;
    margin-top: 6px;
    box-shadow: none;
}
.form-btn:hover {
    background-color: rgba(255, 255, 255, 0.16);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.25);
}
.checkbox-label {
    font-size: 11px;
    color: #cccccc;
}
textview, textview text {
    background-color: rgba(45, 45, 45, 0.9);
    color: #ffffff;
    font-size: 12px;
}
"""
