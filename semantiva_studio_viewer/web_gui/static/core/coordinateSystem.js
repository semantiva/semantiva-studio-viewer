/**
 * CoordinateSystem
 *
 * Small helper to convert coordinates between client (viewport), container-local
 * (the DOM element that contains the graph and the SVG) and optional logical
 * coordinates (pre-scale) when a uniform scale is applied to the container.
 *
 * Usage (later integration):
 *  const cs = new CoordinateSystem();
 *  cs.setContainer(containerEl);
 *  // If UI applies zoom via CSS scale to the container, let the helper know:
 *  cs.setScale(zoomLevel);
 *  // Get a callout DOM element coordinates in container space:
 *  const rect = cs.elementToContainer(calloutEl);
 *
 * The methods intentionally use getBoundingClientRect() so they reflect the
 * real visual layout (including page scrolling and CSS transforms). The
 * "container-local" coordinates returned are in the same pixel space the
 * SVG (placed as child of the container) can use directly.
 */

class CoordinateSystem {
  constructor() {
    this.container = null;
    // scale is the uniform CSS scale applied to the container (default 1)
    // If you don't use logical/pre-scale conversions you can ignore this.
    this.scale = 1;
  }

  /** Set the container element (the shared parent of nodes and SVG) */
  setContainer(containerElement) {
    this.container = containerElement || null;
  }

  /** Get the last measured container client rect or a safe default */
  getContainerRect() {
    if (!this.container) return { left: 0, top: 0, width: 0, height: 0 };
    return this.container.getBoundingClientRect();
  }

  /** Set/get uniform scale (zoom) applied to the container via CSS transform: scale(s) */
  setScale(s) {
    this.scale = typeof s === 'number' && isFinite(s) ? s : 1;
  }

  getScale() {
    return this.scale || 1;
  }

  /** Convert a DOMRect-like object (left, top, width, height) to container-local coordinates */
  domRectToContainer(rect) {
    const containerRect = this.getContainerRect();
    return {
      x: rect.left - containerRect.left,
      y: rect.top - containerRect.top,
      width: rect.width,
      height: rect.height
    };
  }

  /** Convenience: measure an element and return container-local rect */
  elementToContainer(el) {
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return this.domRectToContainer(rect);
  }

  /** Convert client (viewport) point to container-local point */
  clientToContainerPoint(clientX, clientY) {
    const containerRect = this.getContainerRect();
    return { x: clientX - containerRect.left, y: clientY - containerRect.top };
  }

  /** Convert container-local point to client (viewport) point */
  containerToClientPoint(x, y) {
    const containerRect = this.getContainerRect();
    return { clientX: x + containerRect.left, clientY: y + containerRect.top };
  }

  /** Convert from container-local (post-scale) to logical (pre-scale) coordinates */
  containerToLogicalPoint(x, y) {
    const s = this.getScale();
    if (!s || s === 1) return { x, y };
    return { x: x / s, y: y / s };
  }

  /** Convert from logical (pre-scale) to container-local (post-scale) coordinates */
  logicalToContainerPoint(x, y) {
    const s = this.getScale();
    if (!s || s === 1) return { x, y };
    return { x: x * s, y: y * s };
  }

  /**
   * Helper: convert element bounding box to both container-local and logical coords
   * Returns { container: {x,y,width,height}, logical: {x,y,width,height} }
   */
  elementToBoth(el) {
    const c = this.elementToContainer(el);
    if (!c) return null;
    const l = this.containerToLogicalRect(c);
    return { container: c, logical: l };
  }

  containerToLogicalRect(r) {
    const topLeft = this.containerToLogicalPoint(r.x, r.y);
    const s = this.getScale() || 1;
    return {
      x: topLeft.x,
      y: topLeft.y,
      width: r.width / s,
      height: r.height / s
    };
  }

  logicalToContainerRect(r) {
    const topLeft = this.logicalToContainerPoint(r.x, r.y);
    const s = this.getScale() || 1;
    return {
      x: topLeft.x,
      y: topLeft.y,
      width: r.width * s,
      height: r.height * s
    };
  }

  /**
   * Convenience: produce a simple anchor object for connectors
   * shape: { left, top, width, height } (DOMRect-like) OR DOM element
   * returns: { leftX, rightX, centerY, width, height }
   */
  anchorFrom(elOrRect) {
    let rect;
    if (!elOrRect) return null;
    if (elOrRect.getBoundingClientRect) {
      rect = this.elementToContainer(elOrRect);
    } else if (typeof elOrRect.left === 'number') {
      rect = this.domRectToContainer(elOrRect);
    } else {
      return null;
    }
    return {
      leftX: rect.x,
      rightX: rect.x + rect.width,
      centerY: rect.y + rect.height / 2,
      width: rect.width,
      height: rect.height
    };
  }
}

// Expose globally for gradual integration similar to other helpers in the project
window.CoordinateSystem = CoordinateSystem;

export default CoordinateSystem;
