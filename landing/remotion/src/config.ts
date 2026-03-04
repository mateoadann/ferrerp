/*
 * Constantes compartidas del video demo de FerrERP.
 *
 * Archivo separado para evitar dependencias circulares
 * (Demo.tsx importa escenas, escenas importan colores).
 */

/* Colores — idénticos a la app real (custom.css) */
export const colores = {
    primary: '#E07B54',
    primaryHover: '#D06A43',
    primaryForeground: '#FFFFFF',
    secondary: '#0D6E6E',
    sidebar: '#1F2937',
    sidebarForeground: '#F9FAFB',
    sidebarMuted: '#9CA3AF',
    sidebarHover: '#374151',
    background: '#FAFAFA',
    surface: '#FFFFFF',
    foreground: '#1A1A1A',
    foregroundSecondary: '#666666',
    foregroundMuted: '#888888',
    border: '#E5E5E5',
    borderMuted: '#F0F0F0',
    muted: '#F5F5F5',
    success: '#16A34A',
    successBg: '#DCFCE7',
    warning: '#F59E0B',
    warningBg: '#FEF3C7',
    error: '#DC2626',
    errorBg: '#FEE2E2',
};

/*
 * Items del sidebar — réplica exacta de la app.
 * Los íconos corresponden a Material Symbols Rounded (se renderizan
 * con la fuente cargada en loadFonts()).
 */
export const sidebarItems = [
    { icon: 'dashboard', label: 'Dashboard' },
    { icon: 'inventory_2', label: 'Productos' },
    { icon: 'warehouse', label: 'Inventario' },
    { icon: 'shopping_cart', label: 'Compras' },
    { icon: 'point_of_sale', label: 'POS' },
    { icon: 'receipt_long', label: 'Ventas' },
    { icon: 'description', label: 'Presupuestos' },
    { icon: 'receipt', label: 'Facturación' },
    { icon: 'group', label: 'Clientes' },
    { icon: 'payments', label: 'Caja' },
    { icon: 'bar_chart', label: 'Reportes' },
    { icon: 'settings', label: 'Configuración' },
];

export const fontFamily = 'Inter, -apple-system, BlinkMacSystemFont, sans-serif';
export const iconFontFamily = 'Material Symbols Rounded';

/*
 * Cargar las fuentes. Se llama una vez desde Demo.tsx.
 * Material Symbols se carga como archivo local (public/) para que
 * Remotion la tenga disponible al renderizar stills.
 */
export const loadFonts = () => {
    const inter = document.createElement('link');
    inter.rel = 'stylesheet';
    inter.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap';
    document.head.appendChild(inter);

    const style = document.createElement('style');
    style.textContent = `
        @font-face {
            font-family: 'Material Symbols Rounded';
            src: url('/public/MaterialSymbolsRounded.ttf') format('truetype');
            font-weight: 400;
            font-style: normal;
        }
    `;
    document.head.appendChild(style);
};
