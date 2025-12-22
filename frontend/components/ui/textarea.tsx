import * as React from "react"

import { cn } from "@/lib/utils"

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex min-h-[80px] w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 ring-offset-white placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-200 dark:bg-white dark:text-gray-900 dark:ring-offset-white dark:placeholder:text-gray-500 dark:focus-visible:ring-gray-950",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }
