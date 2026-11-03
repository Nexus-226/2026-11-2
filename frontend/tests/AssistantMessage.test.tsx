// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import AssistantMessage from "../src/components/chat/AssistantMessage";

afterEach(cleanup);

it("renders model paragraphs, emphasis and lists as semantic content", () => {
  const { container } = render(
    <AssistantMessage
      text={
        "**注意事项**\n\n- 避免牛肉\n- 观察反应\n\n1. 查看配料\n2. 咨询兽医"
      }
    />,
  );
  expect(container.querySelector("strong")?.textContent).toBe("注意事项");
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
  expect(screen.getAllByRole("list")).toHaveLength(2);
  expect(container.textContent).not.toContain("**");
});

it("does not render raw HTML or remote images and only links HTTP(S)", () => {
  const { container } = render(
    <AssistantMessage
      text={
        '<script>alert(1)</script>\n\n<img src="https://example.com/tracker" onerror="alert(1)">\n\n![image](https://example.com/image.png)\n\n[unsafe](javascript:alert) [local](file:///secret) [relative](/admin) [safe](https://example.com/help)'
      }
    />,
  );
  expect(container.querySelector("script, img, iframe")).toBeNull();
  const links = screen.getAllByRole("link");
  expect(links).toHaveLength(1);
  expect(links[0].getAttribute("href")).toBe("https://example.com/help");
  expect(links[0].getAttribute("rel")).toBe("noopener noreferrer");
});
