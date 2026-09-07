import { KINDS, type Kind } from "./kinds";

/**
 * FR-002: a tinted tile carrying the icon **and** the kind as text.
 *
 * The word is in the document whether or not it is on screen, so stripping every style
 * declaration leaves the kind readable — 021 FR-040 applied to a tile.
 */
export function KindTile({ kind, size = "tile" }: { kind: Kind; size?: "tile" | "inline" }) {
  const style = KINDS[kind];
  const box = size === "tile" ? "h-8 w-8 text-[20px]" : "h-5 w-5 text-[14px]";
  return (
    <span className="inline-flex items-center gap-2" data-kind={kind}>
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded ${box}`}
        style={{ background: style.tint, color: style.ink }}
      >
        <style.Icon />
      </span>
      <span className="text-xs" style={{ color: style.ink }}>
        {style.word}
      </span>
    </span>
  );
}
