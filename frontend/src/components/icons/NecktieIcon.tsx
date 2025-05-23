import React from 'react';

const NecktieIcon: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={props.width || "24"}
    height={props.height || "24"}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={props.strokeWidth || "2"}
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M8.5 2C8.5 2 8 4 9 4H15C16 4 15.5 2 15.5 2H8.5Z" />
    <path d="M9 4L6.5 20L12 23L17.5 20L15 4H9Z" />
    <path d="M9.5 4.5L12 6L14.5 4.5" strokeOpacity="0.6" strokeWidth="1.5" />
  </svg>
);

export default NecktieIcon; 