import { useEffect, useState } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { PageHeaderProvider } from "@/contexts/PageHeaderProvider";
import { AutoPageHeader } from "@/components/PageHeader";
import { useModuleConfig } from "@/hooks/useModuleConfig";
import { useVisibleModules } from "@/hooks/queries/useVisibleModules";
import { usePageHeader } from "@/contexts/PageHeaderContext";
import ActionButton from "@/components/ActionButton";
import { Icon } from "@/components/icons";
import type { IconName } from "@/components/icons";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const location = useLocation();

  // Handle escape key to close drawer
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isDrawerOpen) {
        setIsDrawerOpen(false);
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isDrawerOpen]);

  // Close drawer when route changes
  useEffect(() => {
    setIsDrawerOpen(false);
  }, [location.pathname]);

  return (
    <PageHeaderProvider>
      <div className="drawer min-h-screen bg-base-200 text-base-content">
        {/* Hidden checkbox for drawer control */}
        <input
          id="navigation-drawer"
          type="checkbox"
          className="drawer-toggle"
          checked={isDrawerOpen}
          onChange={() => setIsDrawerOpen(!isDrawerOpen)}
        />

        {/* Drawer content */}
        <div className="drawer-content flex w-full min-w-0 max-w-full flex-col">
          <AppBar onMenuClick={() => setIsDrawerOpen(true)} />

          {/* Page content area */}
          <main
            style={{ paddingTop: "var(--appbar-height)" }}
            className="flex-1 min-w-0 overflow-hidden xl:pl-[calc(var(--rail-width))]"
          >
            <AutoPageHeader />
            <div className="h-full overflow-y-auto">{children}</div>
          </main>
        </div>

        {/* Drawer side - only visible on mobile and medium screens */}
        <div className="drawer-side xl:hidden">
          <label
            htmlFor="navigation-drawer"
            className="drawer-overlay"
            onClick={() => setIsDrawerOpen(false)}
          ></label>
          <NavigationRail onItemClick={() => setIsDrawerOpen(false)} />
        </div>

        {/* Desktop sidebar - only visible on extra large screens */}
        <div className="hidden xl:block xl:fixed xl:left-0 xl:top-[var(--appbar-height)] xl:bottom-0 xl:z-sidebar">
          <NavigationRail />
        </div>
      </div>
    </PageHeaderProvider>
  );
}

interface NavigationRailProps {
  onItemClick?: () => void;
}

function NavigationRail({ onItemClick }: NavigationRailProps) {
  const { t } = useTranslation();
  const location = useLocation();
  const visible = useVisibleModules();
  const { navModules } = useModuleConfig();

  const visibleSet = new Set(visible.visibleKeys);
  const items = navModules
    .filter((m) => visibleSet.has(m.key))
    .map((m) => ({
      path: m.path,
      navLabel: m.navLabel,
      iconName: m.iconName,
    }));

  return (
    <aside className="w-28 md:w-32 lg:w-36 h-full bg-base-100 shadow-sm">
      <div className="h-full flex flex-col">
        {/* Navigation items - scrollable area with flexible height */}
        <div
          className="overflow-y-auto py-3 min-h-0"
          style={{
            height: "calc(100% - 100px)",
            minHeight: "200px",
          }}
        >
          {items.map((item) => {
            const iconName: IconName | undefined = item.iconName;
            const active = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onItemClick}
                preload="intent"
                className={`flex items-center gap-3 px-3 py-3 w-full text-base-content ${
                  active
                    ? "text-primary bg-primary/10"
                    : "transition-colors hover:bg-primary/10 hover:text-primary"
                }`}
                activeProps={{
                  className: "text-primary bg-primary/10",
                }}
              >
                {iconName ? (
                  <Icon
                    name={iconName}
                    size={20}
                    className="text-base-content/80"
                    aria-hidden
                  />
                ) : null}
                <span className="truncate text-base-content text-base">
                  {item.navLabel}
                </span>
              </Link>
            );
          })}
        </div>

        {/* User section - fixed height at bottom */}
        <div
          className="border-t border-base-300 p-3 bg-base-100"
          style={{ height: "100px", minHeight: "100px" }}
        >
          <div className="h-full flex flex-col justify-center">
            <div className="text-sm font-medium text-base-content/70 text-center py-1">
              Web UI
            </div>
            <div className="text-xs text-base-content/50 text-center">
              {t("common.user")}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

interface AppBarProps {
  onMenuClick: () => void;
}

function AppBar({ onMenuClick }: AppBarProps) {
  const { t } = useTranslation();
  const { title, subtitle, actions } = usePageHeader();

  return (
    <header
      className="fixed top-0 inset-x-0 z-header bg-base-100/80 backdrop-blur supports-[backdrop-filter]:bg-base-100/60 border-base-300 shadow-sm"
      style={{ height: "var(--appbar-height)" }}
    >
      <div className="h-full flex items-center justify-between px-2 xs:px-3 md:px-4 lg:px-6">
        <div className="flex items-center gap-3 min-w-0">
          {/* Mobile menu button */}
          <ActionButton
            label={t("common.openNavigationMenu")}
            icon={
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                className="inline-block w-6 h-6 stroke-current"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            }
            onClick={onMenuClick}
            ariaLabel={t("common.openNavigationMenu")}
            size="md"
            variant="ghost"
            iconOnly
            shape="square"
            className="xl:hidden min-h-12 min-w-12 md:min-h-10 md:min-w-10"
          />

          <div className="hidden lg:flex items-center gap-2 font-bold truncate">
            <Icon name="map" size={20} className="text-primary" aria-hidden />
            <span className="truncate text-xl">LifeOS</span>
          </div>
        </div>

        {/* Center: dynamic page header */}
        <div className="flex-1 min-w-0 px-1 xs:px-0 md:px-4 lg:px-6">
          {title && (
            <div className="flex items-center gap-1 xs:gap-2 md:gap-3 lg:gap-4 min-w-0">
              <div className="truncate text-base-content text-sm xs:text-base md:text-lg lg:text-xl font-semibold flex-shrink min-w-0">
                {title}
              </div>
              {subtitle && (
                <div className="truncate text-base-content text-xs md:text-sm lg:text-base hidden sm:block flex-shrink min-w-0">
                  {subtitle}
                </div>
              )}
              {actions && (
                <div className="ml-auto flex min-w-0 max-w-full flex-shrink gap-1 overflow-x-auto xs:gap-1 md:gap-2 lg:gap-3">
                  {actions}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
