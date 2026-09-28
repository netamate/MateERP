import type { ElementType } from "react";

type MateERPBrandProps = {
  className?: string;
  logoClassName?: string;
  wordmarkClassName?: string;
  heading?: boolean;
};

export function MateERPLogoMark({ className = "" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 521 494"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M2 81V490H87L88 279L310 490L308 373L2 81Z"
        fill="currentColor"
      />
      <path
        d="M91 3L90 120L304 324L432 202L433 413H517L518 4L303 207L91 3Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function MateERPBrand({
  className = "",
  logoClassName = "",
  wordmarkClassName = "",
  heading = false,
}: MateERPBrandProps) {
  const Wordmark: ElementType = heading ? "h1" : "div";

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <MateERPLogoMark className={logoClassName} />
      <div className="min-w-0">
        <Wordmark className={`mateerp-wordmark leading-none ${wordmarkClassName}`}>
          MateERP
        </Wordmark>
      </div>
    </div>
  );
}
