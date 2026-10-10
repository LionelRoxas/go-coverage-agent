package stats

import (
	"math"
	"strings"
	"testing"
	"time"
)

func loadApproxEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if math.Abs(a[i]-b[i]) > 1e-9 {
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
		{
			name:  "uint slice",
			input: []uint{1, 2, 3},
			want:  Float64Data{1, 2, 3},
		},
		{
			name:  "bool slice",
			input: []bool{true, false, true},
			want:  Float64Data{1, 0, 1},
		},
		{
			name:  "int slice",
			input: []int{-1, 0, 5},
			want:  Float64Data{-1, 0, 5},
		},
		{
			name:  "string slice with parseable and non‑parseable",
			input: []string{"1.5", "-2", "foo"},
			want:  Float64Data{1.5, -2},
		},
		{
			name:  "raw string",
			input: "3.0 abc 4",
			want:  Float64Data{3, 4},
		},
		{
			name:  "io.Reader",
			input: strings.NewReader("1 2\n3 4"),
			want:  Float64Data{1, 2, 3, 4},
		},
		{
			name:  "map[int]int sequential keys",
			input: map[int]int{0: 5, 1: 6},
			want:  Float64Data{5, 6},
		},
		{
			name:  "map[int]bool sequential keys",
			input: map[int]bool{0: true, 1: false, 2: true},
			want:  Float64Data{1, 0, 1},
		},
		{
			name:  "[]interface{} mixed types",
			input: []interface{}{int(7), "8.5", false, time.Duration(3)},
			want:  Float64Data{7, 8.5, 0, 3},
		},
		{
			name:  "time.Duration slice",
			input: []time.Duration{time.Second, 500 * time.Millisecond},
			want:  Float64Data{float64(time.Second), float64(500 * time.Millisecond)},
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got := LoadRawData(tc.input)
			if !loadApproxEqual(got, tc.want) {
				t.Errorf("LoadRawData(%v) = %v, want %v", tc.input, got, tc.want)
			}
		})
	}
}

func TestLoadRawData_Uncovered(t *testing.T) {
	cases := []struct {
		name string
		raw  interface{}
		want Float64Data
	}{
		{"uint8 slice", []uint8{1, 2, 255}, Float64Data{1, 2, 255}},
		{"uint16 slice", []uint16{65535, 0}, Float64Data{65535, 0}},
		{"uint32 slice", []uint32{4294967295}, Float64Data{4294967295}},
		{"uint64 slice", []uint64{12345}, Float64Data{12345}},
		{"int8 slice", []int8{-128, 0, 127}, Float64Data{-128, 0, 127}},
		{"int16 slice", []int16{-32768, 32767}, Float64Data{-32768, 32767}},
		{"int32 slice", []int32{-2147483648, 2147483647}, Float64Data{-2147483648, 2147483647}},
		{"int64 slice", []int64{-1234567890123, 1234567890123}, Float64Data{-1234567890123, 1234567890123}},
		{"float64 slice", []float64{1.5, -2.3}, Float64Data{1.5, -2.3}},
		{"map int int8", map[int]int8{0: -1, 1: 0, 2: 1}, Float64Data{-1, 0, 1}},
		{"map int int16", map[int]int16{0: -300, 1: 300}, Float64Data{-300, 300}},
		{"map int int32", map[int]int32{0: -2000000000, 1: 2000000000}, Float64Data{-2000000000, 2000000000}},
		{"map int int64", map[int]int64{0: -1234567890123, 1: 1234567890123}, Float64Data{-1234567890123, 1234567890123}},
		{"map int string", map[int]string{0: "1.5", 1: "-2.5"}, Float64Data{1.5, -2.5}},
		{"map int uint", map[int]uint{0: 5, 1: 10}, Float64Data{5, 10}},
		{"map int uint8", map[int]uint8{0: 7, 1: 8}, Float64Data{7, 8}},
		{"map int uint16", map[int]uint16{0: 9, 1: 10}, Float64Data{9, 10}},
		{"map int uint32", map[int]uint32{0: 11, 1: 12}, Float64Data{11, 12}},
		{"map int uint64", map[int]uint64{0: 13, 1: 14}, Float64Data{13, 14}},
		{"map int float64", map[int]float64{0: 3.14, 1: -1.0}, Float64Data{3.14, -1.0}},
		{"map int time.Duration", map[int]time.Duration{0: time.Second, 1: 2 * time.Second}, Float64Data{float64(time.Second), float64(2 * time.Second)}},
		{"slice interface bools", []interface{}{true, false, true}, Float64Data{1, 0, 1}},
		{"slice interface uint", []interface{}{uint(5), uint(10)}, Float64Data{5, 10}},
		{"slice interface float64", []interface{}{float64(2.5), float64(-3.5)}, Float64Data{2.5, -3.5}},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := LoadRawData(tc.raw)
			if !loadApproxEqual(got, tc.want) {
				t.Errorf("LoadRawData(%v) = %v, want %v", tc.raw, got, tc.want)
			}
		})
	}
}
