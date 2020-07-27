import React from "react";
import { VisualizationType, registeredVisualizations } from "@redash/viz/lib";

import "./VisualizationName.less";

function VisualizationName({ visualization, queryName }) {
  const config = registeredVisualizations[visualization.type];
  const widgetTitle = visualization.options.widgetTitle;

  if (widgetTitle === "hide") {
    return null;
  } else if (widgetTitle === "viz") {
    return (
      <span className="visualization-name">
        {config && visualization.name !== config.name ? visualization.name : null}
      </span>
    );
  } else if (widgetTitle === "query") {
    return (
      <span className="visualization-name">
        {queryName}
      </span>
    );
  } else {
    return (
      <>
        <span className="visualization-name">
          {config && visualization.name !== config.name ? visualization.name : null}
        </span>
        <span className="query-name">
          {queryName}
        </span>
      </>
    );
  }
}

VisualizationName.propTypes = {
  visualization: VisualizationType.isRequired,
};

export default VisualizationName;
