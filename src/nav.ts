// Where B (back) leads from the plugin's pages. Pages opened from the Quick Access
// panel return to that panel; a page opened from another page returns to that page.
import { Navigation, QuickAccessTab } from "@decky/ui";

const stack: boolean[] = []; // true: the page was opened from the Quick Access panel

/** Opens a page from the Quick Access panel. */
export function openFromPanel(route: string) {
  stack.length = 0;
  stack.push(true);
  Navigation.Navigate(route);
  Navigation.CloseSideMenus(); // after Navigate, as recommended by @decky/ui
}

/** Opens a page from another page of the plugin. */
export function openPage(route: string) {
  stack.push(false);
  Navigation.Navigate(route);
}

/** B on a plugin page: back to where the page was opened from. */
export function goBack() {
  const fromPanel = stack.pop() ?? false;
  Navigation.NavigateBack();
  if (fromPanel) setTimeout(() => Navigation.OpenQuickAccessMenu(QuickAccessTab.Decky), 50);
}
