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
