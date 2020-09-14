import { find, isArray, get, first, includes, map, intersection, isEqual, isEmpty } from "lodash";
import React from "react";
import PropTypes from "prop-types";
import Select from "antd/lib/select";

const { Option } = Select;
const ALL_VALUES = "###Redash::QueryBasedParameters::SelectAll###";
const NONE_VALUES = "###Redash::QueryBasedParameters::Clear###";

export default class QueryBasedParameterInput extends React.Component {
  static propTypes = {
    parameter: PropTypes.any, // eslint-disable-line react/forbid-prop-types
    value: PropTypes.any, // eslint-disable-line react/forbid-prop-types
    mode: PropTypes.oneOf(["default", "multiple"]),
    queryId: PropTypes.number,
    onSelect: PropTypes.func,
    className: PropTypes.string,
  };

  static defaultProps = {
    value: null,
    mode: "default",
    parameter: null,
    queryId: null,
    onSelect: () => {},
    className: "",
  };

  constructor(props) {
    super(props);
    this.state = {
      options: [],
      value: null,
      loading: false,
    };
  }

  componentDidMount() {
    this._loadOptions(this.props.queryId);
  }

  componentDidUpdate(prevProps) {
    if (this.props.queryId !== prevProps.queryId) {
      this._loadOptions(this.props.queryId);
    }
    if (this.props.value !== prevProps.value) {
      this.setValue(this.props.value);
    }
  }

  setValue(value) {
    const { options } = this.state;
    if (this.props.mode === "multiple") {
      value = isArray(value) ? value : [value];
      const optionValues = map(options, option => option.value);
      const validValues = intersection(value, optionValues);
      this.setState({ value: validValues });
      return validValues;
    }
    const found = find(options, option => option.value === this.props.value) !== undefined;
    value = found ? value : get(first(options), "value");
    this.setState({ value });
    return value;
  }

  async _loadOptions(queryId) {
    if (queryId && queryId !== this.state.queryId) {
      this.setState({ loading: true });
      const options = await this.props.parameter.loadDropdownValues();

      // stale queryId check
      if (this.props.queryId === queryId) {
        this.setState({ options, loading: false }, () => {
          const updatedValue = this.setValue(this.props.value);
          if (!isEqual(updatedValue, this.props.value)) {
            this.props.onSelect(updatedValue);
          }
        });
      }
    }
  }

  render() {
    const { className, value, mode, onSelect, ...otherProps } = this.props;
    const { loading, options } = this.state;

    const onChange = (value) => {
      if (mode === "multiple" && includes(value, ALL_VALUES)) {
        value = [...map(options, option => option.value)];
      }
      if (mode === "multiple" && includes(value, NONE_VALUES)) {
        value = [];
      }
      onSelect(value);
    }

    return (
      <span>
        <Select
          className={className}
          disabled={loading}
          loading={loading}
          mode={mode}
          value={this.state.value}
          onChange={onChange}
          dropdownMatchSelectWidth={false}
          optionFilterProp="children"
          showSearch
          showArrow={mode !== "multiple"}
          allowClear={mode === "multiple"}
          notFoundContent={isEmpty(options) ? "No options available" : null}
          {...otherProps}>
          {mode !== "multiple" && options.map(option => (
            <Option value={option.value} key={option.value}>
              {option.name}
            </Option>
          ))}
          {mode === "multiple" && [
            <Select.Option key={NONE_VALUES} data-test="ClearOption">
              <i className="fa fa-square-o m-r-5" />
              Clear
            </Select.Option>,
            <Select.Option key={ALL_VALUES} data-test="SelectAllOption">
              <i className="fa fa-check-square-o m-r-5" />
              Select All
            </Select.Option>,
            <Select.OptGroup key="Values" title="Values">
              {options.map(option => (
                <Option value={option.value} key={option.value}>
                  {option.name}
                </Option>
              ))}
            </Select.OptGroup>,
          ]}
        </Select>
      </span>
    );
  }
}
