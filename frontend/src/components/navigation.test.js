import { describe, expect, it } from "vitest";
import { NAV, ICONS, ROLE_LABEL } from "./navigation";
import { ROLE_HOME } from "../context/AuthContext";

describe("menus", () => {
  it("every menu item has an icon that exists, a path under its role's home, and a label", () => {
    for (const [role, items] of Object.entries(NAV)) {
      expect(ROLE_HOME[role], `home of ${role}`).toBeTruthy();
      expect(ROLE_LABEL[role], `label of ${role}`).toBeTruthy();
      for (const [path, label, icon] of items) {
        expect(path.startsWith(ROLE_HOME[role]), `${role}: ${path}`).toBe(true);
        expect(label).toBeTruthy();
        expect(ICONS[icon], `${role} menu icon ${icon}`).toBeTruthy();
      }
    }
  });
  it("every login role has a menu", () => {
    for (const role of Object.keys(ROLE_HOME)) expect(NAV[role], role).toBeTruthy();
  });
});

import { PERMISSION_MENU, menuFor } from "./navigation";

describe("pages that follow permissions", () => {
  it("every permission page has an icon that exists", () => {
    for (const [perms, path, label, icon] of PERMISSION_MENU) {
      expect(perms.length).toBeGreaterThan(0);
      expect(path.startsWith("/")).toBe(true);
      expect(label).toBeTruthy();
      expect(ICONS[icon], icon).toBeTruthy();
    }
  });
  it("a login gets the pages its permissions open, before My Profile, and nothing else", () => {
    const store = menuFor({ role: "EMPLOYEE", permissions: ["bloodbank.manage", "procure.request"] }).map(([to]) => to);
    expect(store).toContain("/bloodbank");
    expect(store).toContain("/procurement");
    expect(store).not.toContain("/stock");
    expect(store.at(-1)).toBe("/employee/profile");
    expect(menuFor({ role: "PATIENT", permissions: [] })).toEqual(NAV.PATIENT);
  });
  it("a page is not added twice", () => {
    const paths = menuFor({ role: "PHARMACY", permissions: ["stock.view", "stock.manage"] }).map(([to]) => to);
    expect(paths.filter((p) => p === "/stock")).toHaveLength(1);
  });
});
