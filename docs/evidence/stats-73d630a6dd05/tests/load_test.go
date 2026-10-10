package stats

import (
	"math"
	"strings"
	"testing"
	"time"
)

func loadApproxEqual(got, want Float64Data) bool {
	if len(got) != len(want) {
		return false
	}
	for i := range got {
		if math.Abs(got[i]-want[i]) > 1e-9 {
			return false
		}
	}
	return true
}

func TestLoadRawData(t *testing.T) {
	cases := []struct {
		name  string
		input interface{}
		want  Float64Data
	}{
		{"UintSlice", []uint{1, 2, 3}, Float64Data{1, 2, 3}},
		{"Uint8Slice", []uint8{4, 5}, Float64Data{4, 5}},
		{"Uint16Slice", []uint16{6}, Float64Data{6}},
		{"Uint32Slice", []uint32{7}, Float64Data{7}},
		{"Uint64Slice", []uint64{8}, Float64Data{8}},
		{"BoolSlice", []bool{true, false, true}, Float64Data{1, 0, 1}},
		{"IntSlice", []int{-1, 0, 2}, Float64Data{-1, 0, 2}},
		{"Int8Slice", []int8{-3, 4}, Float64Data{-3, 4}},
		{"Int16Slice", []int16{5}, Float64Data{5}},
		{"Int32Slice", []int32{-6}, Float64Data{-6}},
		{"Int64Slice", []int64{7}, Float64Data{7}},
		{"Float64Slice", []float64{1.1, 2.2}, Float64Data{1.1, 2.2}},
		{"StringSlice", []string{"1.5", "abc", "2"}, Float64Data{1.5, 2}},
		{"DurationSlice", []time.Duration{time.Second, 2 * time.Second}, Float64Data{float64(time.Second), float64(2 * time.Second)}},
		{"MapIntInt", map[int]int{0: 10, 1: 20}, Float64Data{10, 20}},
		{"MapIntString", map[int]string{0: "5.5", 1: "x"}, Float64Data{5.5}},
		{"MapIntBool", map[int]bool{0: true, 1: false, 2: true}, Float64Data{1, 0, 1}},
		{"MapIntFloat64", map[int]float64{0: 9.9, 1: 10.1}, Float64Data{9.9, 10.1}},
		{"MapIntDuration", map[int]time.Duration{0: time.Millisecond, 1: 2 * time.Millisecond}, Float64Data{float64(time.Millisecond), float64(2 * time.Millisecond)}},
		{"StringInput", "3.14 abc 2", Float64Data{3.14, 2}},
		{"ReaderInput", strings.NewReader("4 5.5 xyz"), Float64Data{4, 5.5}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := LoadRawData(tc.input)
			if !loadApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result for %s: got %v want %v", tc.name, got, tc.want)
			}
		})
	}
}

func TestLoadRawData_Uncovered(t *testing.T) {
	tests := []struct {
		name string
		raw  interface{}
		want []float64
	}{
		{
			name: "slice_interface_mixed",
			raw:  []interface{}{int(1), uint(2), float64(3.5), true, false, time.Duration(5)},
			want: []float64{1, 2, 3.5, 1, 0, 5},
		},
		{
			name: "map_int8",
			raw:  map[int]int8{0: -1, 1: 2},
			want: []float64{-1, 2},
		},
		{
			name: "map_int16",
			raw:  map[int]int16{0: -10, 1: 20},
			want: []float64{-10, 20},
		},
		{
			name: "map_int32",
			raw:  map[int]int32{0: -100, 1: 200},
			want: []float64{-100, 200},
		},
		{
			name: "map_int64",
			raw:  map[int]int64{0: -1000, 1: 2000},
			want: []float64{-1000, 2000},
		},
		{
			name: "map_uint",
			raw:  map[int]uint{0: 1, 1: 2},
			want: []float64{1, 2},
		},
		{
			name: "map_uint8",
			raw:  map[int]uint8{0: 3, 1: 4},
			want: []float64{3, 4},
		},
		{
			name: "map_uint16",
			raw:  map[int]uint16{0: 5, 1: 6},
			want: []float64{5, 6},
		},
		{
			name: "map_uint32",
			raw:  map[int]uint32{0: 7, 1: 8},
			want: []float64{7, 8},
		},
		{
			name: "map_uint64",
			raw:  map[int]uint64{0: 9, 1: 10},
			want: []float64{9, 10},
		},
	}
	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := LoadRawData(tc.raw)
			want := Float64Data(tc.want)
			if !loadApproxEqual(got, want) {
				t.Fatalf("unexpected result: got %v, want %v", got, want)
			}
		})
	}
}
