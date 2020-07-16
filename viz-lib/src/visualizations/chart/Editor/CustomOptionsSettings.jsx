import { isNil } from "lodash";
import React from "react";
import { Section, TextArea } from "@/components/visualizations/editor";
import { EditorPropTypes } from "@/visualizations/prop-types";

export default function CustomOptionsSettings({ options, onOptionsChange }) {
  return (
    <React.Fragment>
      <Section>
        <TextArea
          label="Custom Plotly data options (JSON)"
          rows="10"
          defaultValue={isNil(options.customDataOptionsJson) ? '{}' : options.customDataOptionsJson}
          onBlur={event => onOptionsChange({ customDataOptionsJson: event.target.value })}
          className="visualization-editor-text-area-monospace"
        />
      </Section>

      <Section>
        <TextArea
          label="Custom Plotly layout options (JSON)"
          rows="10"
          defaultValue={isNil(options.customLayoutOptionsJson) ? '{}' : options.customLayoutOptionsJson}
          onBlur={event => onOptionsChange({ customLayoutOptionsJson: event.target.value })}
          className="visualization-editor-text-area-monospace"
        />
      </Section>
    </React.Fragment>
  );
}

CustomOptionsSettings.propTypes = EditorPropTypes;
