import React, { useRef, useState } from 'react';
import './SwipeToAction.css';

interface SwipeToActionProps {
  children: React.ReactNode;
  onSwipeRight?: () => void;
  onSwipeLeft?: () => void;
}

export const SwipeToAction: React.FC<SwipeToActionProps> = ({ children, onSwipeRight, onSwipeLeft }) => {
  const [translateX, setTranslateX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  
  const startX = useRef(0);
  const cardRef = useRef<HTMLDivElement>(null);
  
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    setIsDragging(true);
    startX.current = e.clientX - translateX;
    if (cardRef.current) {
      cardRef.current.setPointerCapture(e.pointerId);
    }
  };
  
  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    const currentX = e.clientX - startX.current;
    setTranslateX(currentX);
  };
  
  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    setIsDragging(false);
    if (cardRef.current) {
      cardRef.current.releasePointerCapture(e.pointerId);
    }
    
    // Action zones trigger logic
    if (translateX > 90) {
      if (onSwipeRight) onSwipeRight();
    } else if (translateX < -90) {
      if (onSwipeLeft) onSwipeLeft();
    }
    
    // Snap back in all scenarios
    setTranslateX(0);
  };
  
  return (
    <div className="swipe-container">
      {/* Background Actions */}
      <div className="swipe-actions">
        {/* Load Action (Left side, revealed on right swipe) */}
        <div className={`swipe-action-left action-load ${translateX > 0 ? 'visible' : 'hidden'}`}>
          <span>Load</span>
        </div>
        {/* Report Action (Right side, revealed on left swipe) */}
        <div className={`swipe-action-right action-report ${translateX < 0 ? 'visible' : 'hidden'}`}>
          <span>Report</span>
        </div>
      </div>
      
      {/* Draggable Card */}
      <div 
        ref={cardRef}
        className={`swipe-card ${isDragging ? 'dragging' : 'snapping'}`}
        style={{ transform: `translateX(${translateX}px)` }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        {children}
      </div>
    </div>
  );
};
