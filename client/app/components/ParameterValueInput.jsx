import { includes, isEqual, isEmpty, map } from "lodash";
import React from "react";
import PropTypes from "prop-types";
import Select from "antd/lib/select";
import Input from "antd/lib/input";
import InputNumber from "antd/lib/input-number";
import DateParameter from "@/components/dynamic-parameters/DateParameter";
import DateRangeParameter from "@/components/dynamic-parameters/DateRangeParameter";
import QueryBasedParameterInput from "./QueryBasedParameterInput";

import "./ParameterValueInput.less";

const { Option } = Select;
const ALL_VALUES = "###Redash::Parameters::SelectAll###";
const NONE_VALUES = "###Redash::Parameters::Clear###";

const multipleValuesProps = {
  maxTagCount: 3,
  maxTagTextLength: 10,
  maxTagPlaceholder: num => `+${num.length} more`,
};

class ParameterValueInput extends React.Component {
  static propTypes = {
    type: PropTypes.string,
    value: PropTypes.any, // eslint-disable-line react/forbid-prop-types
    enumOptions: PropTypes.string,
    queryId: PropTypes.number,
    parameter: PropTypes.any, // eslint-disable-line react/forbid-prop-types
    onSelect: PropTypes.func,
    className: PropTypes.string,
  };

  static defaultProps = {
    type: "text",
    value: null,
    enumOptions: "",
    queryId: null,
    parameter: null,
    onSelect: () => {},
    className: "",
  };

  constructor(props) {
    super(props);
    this.state = {
      value: props.parameter.hasPendingValue ? props.parameter.pendingValue : props.value,
      isDirty: props.parameter.hasPendingValue,
    };
  }

  componentDidUpdate = prevProps => {
    const { value, parameter } = this.props;
    // if value prop updated, reset dirty state
    if (prevProps.value !== value || prevProps.parameter !== parameter) {
      this.setState({
        value: parameter.hasPendingValue ? parameter.pendingValue : value,
        isDirty: parameter.hasPendingValue,
      });
    }
  };

  onSelect = value => {
    const isDirty = !isEqual(value, this.props.value);
    this.setState({ value, isDirty });
    this.props.onSelect(value, isDirty);
  };

  renderDateParameter() {
    const { type, parameter } = this.props;
    const { value } = this.state;
    return (
      <DateParameter
        type={type}
        className={this.props.className}
        value={value}
        parameter={parameter}
        onSelect={this.onSelect}
      />
    );
  }

  renderDateRangeParameter() {
    const { type, parameter } = this.props;
    const { value } = this.state;
    return (
      <DateRangeParameter
        type={type}
        className={this.props.className}
        value={value}
        parameter={parameter}
        onSelect={this.onSelect}
      />
    );
  }

  renderEnumInput() {
    const { enumOptions, parameter } = this.props;
    const { value } = this.state;
    const enumOptionsArray = enumOptions.split("\n").filter(v => v !== "");
    // Antd Select doesn't handle null in multiple mode
    const normalize = val => (parameter.multiValuesOptions && val === null ? [] : val);

    const onChange = (value) => {
      if (parameter.multiValuesOptions && includes(value, ALL_VALUES)) {
        value = [...map(enumOptionsArray, option => option)];
      }
      if (parameter.multiValuesOptions && includes(value, NONE_VALUES)) {
        value = [];
      }
      this.onSelect(value);
    }

    return (
      <Select
        className={this.props.className}
        mode={parameter.multiValuesOptions ? "multiple" : "default"}

        optionFilterProp="children"
        value={normalize(value)}
        onChange={onChange}
        dropdownMatchSelectWidth={false}
        showSearch
        showArrow={!parameter.multiValuesOptions}
        allowClear={!!parameter.multiValuesOptions}
        style={{ minWidth: 60 }}
        notFoundContent={isEmpty(enumOptionsArray) ? "No options available" : null}
        {...multipleValuesProps}>
        {!parameter.multiValuesOptions && enumOptionsArray.map(option => (
          <Option key={option} value={option}>
            {option}
          </Option>
        ))}
        {parameter.multiValuesOptions && [
          <Select.Option key={NONE_VALUES} data-test="ClearOption">
            <i className="fa fa-square-o m-r-5" />
            Clear
          </Select.Option>,
          <Select.Option key={ALL_VALUES} data-test="SelectAllOption">
            <i className="fa fa-check-square-o m-r-5" />
            Select All
          </Select.Option>,
          <Select.OptGroup key="Values" title="Values">
            {enumOptionsArray.map(option => (
              <Option key={option} value={option}>
                {option}
              </Option>
            ))}
          </Select.OptGroup>,
        ]}
      </Select>
    );
  }

  renderQueryBasedInput() {
    const { queryId, parameter } = this.props;
    const { value } = this.state;
    return (
      <QueryBasedParameterInput
        className={this.props.className}
        mode={parameter.multiValuesOptions ? "multiple" : "default"}
        optionFilterProp="children"
        parameter={parameter}
        value={value}
        queryId={queryId}
        onSelect={this.onSelect}
        style={{ minWidth: 60 }}
        {...multipleValuesProps}
      />
    );
  }

  renderNumberInput() {
    const { className } = this.props;
    const { value } = this.state;

    const normalize = val => (isNaN(val) ? undefined : val);

    return (
      <InputNumber className={className} value={normalize(value)} onChange={val => this.onSelect(normalize(val))} />
    );
  }

  renderTextInput() {
    const { className } = this.props;
    const { value } = this.state;

    return (
      <Input
        className={className}
        value={value}
        data-test="TextParamInput"
        onChange={e => this.onSelect(e.target.value)}
      />
    );
  }

  renderInput() {
    const { type } = this.props;
    switch (type) {
      case "datetime-with-seconds":
      case "datetime-local":
      case "date":
        return this.renderDateParameter();
      case "datetime-range-with-seconds":
      case "datetime-range":
      case "date-range":
        return this.renderDateRangeParameter();
      case "enum":
        return this.renderEnumInput();
      case "query":
        return this.renderQueryBasedInput();
      case "number":
        return this.renderNumberInput();
      default:
        return this.renderTextInput();
    }
  }

  render() {
    const { isDirty } = this.state;

    return (
      <div className="parameter-input" data-dirty={isDirty || null} data-test="ParameterValueInput">
        {this.renderInput()}
      </div>
    );
  }
}

export default ParameterValueInput;
