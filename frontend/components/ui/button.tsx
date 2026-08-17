import { forwardRef } from "react";
import Link from "next/link";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40 active:scale-[0.98] [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
      },
      size: {
        sm: "h-8 px-3",
        md: "h-9 px-4",
        lg: "h-11 px-6 text-md",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

type BaseProps = VariantProps<typeof buttonVariants> & { className?: string };

type ButtonAsButtonProps = BaseProps &
  React.ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined };

type ButtonAsLinkProps = BaseProps &
  Omit<React.ComponentProps<typeof Link>, "className"> & { href: string };

export type ButtonProps = ButtonAsButtonProps | ButtonAsLinkProps;

/**
 * The one button in the system. Renders a semantic <button>, or a Next <Link>
 * when `href` is set (identically styled). Variants/sizes per
 * docs/04-component-guidelines.md. Themed via tokens only.
 */
export const Button = forwardRef<HTMLButtonElement | HTMLAnchorElement, ButtonProps>(
  (props, ref) => {
    const classes = cn(buttonVariants({ variant: props.variant, size: props.size }), props.className);

    if (props.href !== undefined) {
      const { className: _c, variant: _v, size: _s, href, ...rest } = props;
      return <Link ref={ref as React.Ref<HTMLAnchorElement>} href={href} className={classes} {...rest} />;
    }

    const { className: _c, variant: _v, size: _s, href: _h, ...rest } = props;
    return <button ref={ref as React.Ref<HTMLButtonElement>} className={classes} {...rest} />;
  }
);
Button.displayName = "Button";

export { buttonVariants };
