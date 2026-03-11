import * as React from "react";
import { cn } from "@/lib/utils";

export function Badge({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border border-white/60 bg-white/70 px-3 py-1 text-xs font-medium text-muted-foreground",
        className
      )}
      {...props}
    />
  );
}
